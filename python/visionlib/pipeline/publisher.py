import logging
from typing import List, Optional, Tuple

import pybase64
import valkey

from ._backpressure import BackpressureCoordinator, GroupCoordinator

logger = logging.getLogger(__name__)


class ValkeyPublisher:
    def __init__(self, host: str, port: int, stream_maxlen: int = 10, b64_encode: bool = True,
                 enable_backpressure: bool = False, backpressure_threshold: Optional[int] = None,
                 monitor_interval: float = 0.2, consumer_idle_timeout_ms: int = 10_000,
                 fail_open_timeout: Optional[float] = 2.0, **valkey_args) -> None:
        self._valkey_client = None
        self._valkey_args = valkey_args
        self._host = host
        self._port = port
        self._stream_maxlen = stream_maxlen
        self._b64_encode = b64_encode

        # Backpressure configuration. When disabled, the publish path stays fire-and-forget; the
        # only added behavior is that the default consumer group is created on each owned stream.
        self._enable_backpressure = enable_backpressure
        self._backpressure_threshold = (backpressure_threshold if backpressure_threshold is not None
                                        else max(1, stream_maxlen // 2))
        self._monitor_interval = monitor_interval
        self._consumer_idle_timeout_ms = consumer_idle_timeout_ms
        self._fail_open_timeout = fail_open_timeout

        # Dedicated admin connection for group creation and monitoring. It is kept separate from
        # self._valkey_client because the pipeline publisher buffers commands on that client.
        self._admin_client = None
        self._coordinator = None

    def _build_coordinator(self):
        '''Select the coordinator once, based on whether this publisher honours backpressure.'''
        if self._enable_backpressure:
            return BackpressureCoordinator(
                self._admin_client,
                threshold=self._backpressure_threshold,
                monitor_interval=self._monitor_interval,
                consumer_idle_timeout_ms=self._consumer_idle_timeout_ms,
                fail_open_timeout=self._fail_open_timeout,
            )
        return GroupCoordinator(self._admin_client)

    def __enter__(self):
        self._valkey_client = valkey.Valkey(self._host, self._port, **self._valkey_args)
        self._admin_client = valkey.Valkey(self._host, self._port, **self._valkey_args)
        self._coordinator = self._build_coordinator()
        self._coordinator.start()
        return self

    def __call__(self, stream_key: str, proto_data: bytes):
        self._coordinator.await_capacity()
        self._coordinator.ensure_stream(stream_key)
        self._add_to_stream(stream_key, proto_data)

    def _add_to_stream(self, stream_key: str, proto_data: bytes):
        data_field_name = 'proto_data'
        data_field_value = proto_data

        if self._b64_encode:
            data_field_name = 'proto_data_b64'
            data_field_value = pybase64.b64encode(proto_data)

        self._valkey_client.xadd(
            name=stream_key,
            fields={data_field_name: data_field_value},
            maxlen=self._stream_maxlen
        )

    def __exit__(self, _, __, ___):
        self._coordinator.stop()

        try:
            if self._admin_client is not None:
                self._admin_client.close()
        except Exception as e:
            logger.warning('Error while closing valkey admin client', exc_info=e)

        try:
            self._valkey_client.close()
        except Exception as e:
            logger.warning('Error while closing valkey client', exc_info=e)

        return False

class ValkeyPipelinePublisher(ValkeyPublisher):
    '''A version of the Valkey publisher that uses pipelining to make the sending process more efficient.'''

    def __enter__(self):
        # This works because Pipeline is a subclass of Valkey
        self._valkey_client = valkey.Valkey(self._host, self._port, **self._valkey_args).pipeline(transaction=False)
        # Group creation and monitoring must not go through the buffering pipeline client.
        self._admin_client = valkey.Valkey(self._host, self._port, **self._valkey_args)
        self._coordinator = self._build_coordinator()
        self._coordinator.start()
        return self

    def __call__(self, stream_entries: List[Tuple[str, bytes]]):
        self._coordinator.await_capacity()

        for stream_key, proto_data in stream_entries:
            self._coordinator.ensure_stream(stream_key)
            self._add_to_stream(stream_key, proto_data)

        self._valkey_client.execute()
