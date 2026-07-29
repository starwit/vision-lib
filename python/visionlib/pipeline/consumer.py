import logging
import os
import socket
import uuid
from typing import Generator, List, Optional, Tuple

import pybase64
import valkey

from .publisher import DEFAULT_CONSUMER_GROUP

logger = logging.getLogger(__name__)

# TODO In general (this goes for all changes): The added backpressure changes behavior of the consumer and publisher types fundamentally, so we should refactor this such that the _enable_backpressure flag is not used throughout the entire logic to switch to a fundamentally different behavior.
class ValkeyConsumer:
    def __init__(self, host: str, port: int, stream_keys: List[str], b64_decode=True, block=2000,
                 start_at_head: bool = False, enable_backpressure: bool = False,
                 consumer_name: Optional[str] = None) -> None:
        self._valkey_client = None
        self._host = host
        self._port = port
        self._stream_keys = list(stream_keys)
        self._b64_decode = b64_decode
        self._block = block
        self._start_at_head = start_at_head

        # When enabled, the consumer participates in the publisher's backpressure by attaching to the
        # shared consumer group (implemented via a Valkey read group under the hood). This gives
        # round-robin distribution across consumers and lets the publisher sense how far behind we are.
        self._enable_backpressure = enable_backpressure
        self._consumer_name = consumer_name or f'{socket.gethostname()}-{os.getpid()}-{uuid.uuid4().hex[:8]}'

        init_stream_pointer = '$' if not start_at_head else '0'
        self._stream_pointers = {key: init_stream_pointer for key in stream_keys}

    def __enter__(self):
        self._valkey_client = valkey.Valkey(self._host, self._port)
        if self._enable_backpressure:
            self._ensure_groups()
        return self

    def _ensure_groups(self):
        # The publisher normally owns and creates the group, but we create it here too so that a
        # backpressure consumer also works against an old publisher that never created one.
        # start_at_head only takes effect when *this* consumer creates the group; against an existing
        # group the read position is server-side and shared.
        group_id = '0' if self._start_at_head else '$'
        for stream_key in self._stream_keys:
            try:
                self._valkey_client.xgroup_create(stream_key, DEFAULT_CONSUMER_GROUP, id=group_id, mkstream=True)
            except valkey.exceptions.ResponseError as e:
                if 'BUSYGROUP' not in str(e):
                    raise

    def __call__(self) -> Generator[Tuple[str, bytes], None, None]:
        data_field_name = b'proto_data_b64' if self._b64_decode else b'proto_data'

        if self._enable_backpressure:
            yield from self._consume_group(data_field_name)
        else:
            yield from self._consume_plain(data_field_name)

    def _consume_plain(self, data_field_name) -> Generator[Tuple[str, bytes], None, None]:
        while True:
            result = self._valkey_client.xread(
                count=1,
                block=self._block,
                streams=self._stream_pointers
            )

            if result is None or len(result) == 0:
                yield None, None
                continue

            for item in result:
                proto_data = item[1][0][1][data_field_name]
                stream_key = item[0].decode('utf-8')

                self._update_stream_pointers(stream_key, retrieved_id=item[1][0][0].decode('utf-8'))

                if self._b64_decode:
                    yield stream_key, pybase64.b64decode(proto_data, validate=True)
                else:
                    yield stream_key, proto_data

    def _consume_group(self, data_field_name) -> Generator[Tuple[str, bytes], None, None]:
        # NOACK: entries are delivered but never tracked in a pending list. The group's read
        # position advances on delivery, so lag reflects the pure undelivered count and there is
        # nothing to acknowledge. A message in flight when this consumer crashes is not redelivered.
        streams = {key: '>' for key in self._stream_keys}

        while True:
            result = self._valkey_client.xreadgroup(
                DEFAULT_CONSUMER_GROUP,
                self._consumer_name,
                count=1,
                block=self._block,
                streams=streams,
                noack=True,
            )

            if result is None or len(result) == 0:
                yield None, None
                continue

            for item in result:
                entries = item[1]
                if not entries:
                    continue

                proto_data = entries[0][1][data_field_name]
                stream_key = item[0].decode('utf-8')

                if self._b64_decode:
                    yield stream_key, pybase64.b64decode(proto_data, validate=True)
                else:
                    yield stream_key, proto_data

    def _update_stream_pointers(self, stream_key, retrieved_id):
        self._stream_pointers[stream_key] = retrieved_id

        # should only happen on the first ever received message: move all stream pointers away from '$'
        if '$' in self._stream_pointers.values():
            for key in self._stream_pointers:
                if self._stream_pointers[key] == '$':
                    self._stream_pointers[key] = retrieved_id

    def __exit__(self, _, __, ___):
        try:
            self._valkey_client.close()
        except Exception as e:
            logger.warning('Error while closing valkey client', exc_info=e)

        return False
