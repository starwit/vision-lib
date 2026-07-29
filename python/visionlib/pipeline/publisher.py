import logging
import threading
import time
from typing import Callable, List, Optional, Tuple

import pybase64
import valkey
from prometheus_client import Gauge

logger = logging.getLogger(__name__)

# Name of the consumer group that a publisher creates on every stream it owns. This is a
# hardcoded convention so that backpressure-aware consumers can attach without extra configuration.
DEFAULT_CONSUMER_GROUP = 'visionlib-default-group'

# Undelivered entries for the default consumer group, i.e. how far the group is behind the publisher.
STREAM_LAG = Gauge(
    'visionlib_stream_consumer_group_lag',
    'Undelivered entries (lag) of the default consumer group per stream',
    ['stream', 'group'],
)

# Number of consumers currently considered alive in the default consumer group.
STREAM_CONSUMERS = Gauge(
    'visionlib_stream_consumer_group_consumers',
    'Number of live consumers in the default consumer group per stream',
    ['stream', 'group'],
)


def _measure_lag(client: valkey.Valkey, stream_key: str, group: str) -> int:
    '''Return the number of entries the group has not consumed yet (count-based, timestamp-agnostic).

    Uses the group's ``lag`` field, which is exactly ``entries-added - entries-read``. That field
    becomes ``None`` once MAXLEN trimming discards entries the group had not read yet; in that
    (already-degraded) case we fall back to counting the entries still retained after the group's
    last delivered id. The fallback under-reports true lag but yields a finite number so the
    publisher can make progress.
    '''
    try:
        groups = client.xinfo_groups(stream_key)
    except valkey.exceptions.ResponseError:
        # Stream does not exist (yet).
        return 0

    # xinfo_groups returns dicts with str keys but bytes values (client has no decode_responses).
    group_bytes = group.encode('utf-8')
    group_info = next((g for g in groups if g.get('name') == group_bytes), None)
    if group_info is None:
        return 0

    lag = group_info.get('lag')
    if lag is not None:
        return lag

    last_delivered = group_info.get('last-delivered-id', b'0-0')
    if isinstance(last_delivered, bytes):
        last_delivered = last_delivered.decode('utf-8')
    remaining = client.xrange(stream_key, min='(' + last_delivered, max='+')
    return len(remaining)

# TODO Please move all the group related logic into a separate module
class _GroupMonitor(threading.Thread):
    '''Background thread that watches consumer-group lag, exposes it as a metric, cleans up crashed
    consumers, and drives the publisher's backpressure gate.

    It runs independently of the publishing thread on purpose: a producer blocked on backpressure
    cannot cure its own stall (update metrics, remove dead consumers, or fail open), so that work
    must happen out of band.
    '''

    def __init__(self, client: valkey.Valkey, group: str, get_streams: Callable[[], List[str]],
                 threshold: int, idle_timeout_ms: int, interval: float,
                 fail_open_timeout: Optional[float], ok_event: threading.Event) -> None:
        super().__init__(daemon=True)
        self._client = client
        self._group = group
        self._get_streams = get_streams
        self._threshold = threshold
        self._idle_timeout_ms = idle_timeout_ms
        self._interval = interval
        self._fail_open_timeout = fail_open_timeout
        self._ok_event = ok_event
        self._stop_event = threading.Event()
        self._no_consumer_since: Optional[float] = None
        self._fail_open_logged = False

    def run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._tick()
            except Exception as e:
                logger.warning('Error in backpressure monitor', exc_info=e)
            self._stop_event.wait(self._interval)

    def _tick(self) -> None:
        streams = self._get_streams()
        all_below_threshold = True
        total_live_consumers = 0

        for stream_key in streams:
            lag = _measure_lag(self._client, stream_key, self._group)
            STREAM_LAG.labels(stream=stream_key, group=self._group).set(lag)

            live = self._cleanup_dead_consumers(stream_key)
            STREAM_CONSUMERS.labels(stream=stream_key, group=self._group).set(live)
            total_live_consumers += live

            if lag >= self._threshold:
                all_below_threshold = False

        release = all_below_threshold or self._should_fail_open(all_below_threshold, total_live_consumers)

        if release:
            self._ok_event.set()
        else:
            self._ok_event.clear()

    # TODO Does it ever recover from fail_open state?
    def _should_fail_open(self, all_below_threshold: bool, total_live_consumers: int) -> bool:
        '''Release the publisher if it would otherwise block forever with no live consumer left.'''
        blocking = not all_below_threshold
        if self._fail_open_timeout is None or not blocking or total_live_consumers > 0:
            # Strict mode, not blocking, or someone is still consuming: reset the timer.
            self._no_consumer_since = None
            self._fail_open_logged = False
            return False

        now = time.monotonic()
        if self._no_consumer_since is None:
            self._no_consumer_since = now
            return False

        if now - self._no_consumer_since >= self._fail_open_timeout:
            if not self._fail_open_logged:
                logger.warning(
                    'Backpressure: no live consumers for %.1fs, releasing publisher; '
                    'undelivered messages may now be trimmed', self._fail_open_timeout)
                self._fail_open_logged = True
            return True

        return False

    def _cleanup_dead_consumers(self, stream_key: str) -> int:
        '''Remove consumers that have been idle beyond the threshold; return the live consumer count.'''
        try:
            consumers = self._client.xinfo_consumers(stream_key, self._group)
        except valkey.exceptions.ResponseError:
            # Stream or group does not exist (yet).
            return 0

        # xinfo_consumers returns dicts with str keys but bytes values (the consumer name).
        live = 0
        for consumer in consumers:
            idle_ms = consumer.get('idle', 0)
            if idle_ms >= self._idle_timeout_ms:
                self._client.xgroup_delconsumer(stream_key, self._group, consumer['name'])
            else:
                live += 1
        return live

    def stop(self) -> None:
        self._stop_event.set()


class ValkeyPublisher:
    def __init__(self, host: str, port: int, stream_maxlen=10, b64_encode=True,
                 enable_backpressure: bool = False, backpressure_threshold: Optional[int] = None,
                 monitor_interval: float = 0.2, consumer_idle_timeout_ms: int = 10_000,
                 fail_open_timeout: Optional[float] = 10.0, **valkey_args) -> None:
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
        self._monitor: Optional[_GroupMonitor] = None
        self._known_streams = set()
        self._streams_lock = threading.Lock()
        # Set == the publisher may write. Initially open; the monitor clears it when lag is too high.
        self._ok_to_publish = threading.Event()
        self._ok_to_publish.set()

    def __enter__(self):
        self._valkey_client = valkey.Valkey(self._host, self._port, **self._valkey_args)
        self._admin_client = valkey.Valkey(self._host, self._port, **self._valkey_args)
        self._start_monitor()
        return self

    def _start_monitor(self):
        if not self._enable_backpressure:
            return
        self._monitor = _GroupMonitor(
            client=self._admin_client,
            group=DEFAULT_CONSUMER_GROUP,
            get_streams=self._snapshot_streams,
            threshold=self._backpressure_threshold,
            idle_timeout_ms=self._consumer_idle_timeout_ms,
            interval=self._monitor_interval,
            fail_open_timeout=self._fail_open_timeout,
            ok_event=self._ok_to_publish,
        )
        self._monitor.start()

    def _snapshot_streams(self) -> List[str]:
        with self._streams_lock:
            return list(self._known_streams)

    def _ensure_group(self, stream_key: str):
        '''Create the default consumer group on a stream the first time we publish to it.'''
        with self._streams_lock:
            if stream_key in self._known_streams:
                return
        try:
            self._admin_client.xgroup_create(stream_key, DEFAULT_CONSUMER_GROUP, id='$', mkstream=True)
        except valkey.exceptions.ResponseError as e:
            if 'BUSYGROUP' not in str(e):
                raise
        with self._streams_lock:
            self._known_streams.add(stream_key)

    def _await_capacity(self):
        '''Block until the monitor signals there is room in the consumer group (no-op if disabled).'''
        if not self._enable_backpressure:
            return
        self._ok_to_publish.wait()

    def __call__(self, stream_key: str, proto_data: bytes):
        self._await_capacity()
        self._add_to_stream(stream_key, proto_data)

    def _add_to_stream(self, stream_key: str, proto_data: bytes):
        self._ensure_group(stream_key)

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

    def _stop_monitor(self):
        if self._monitor is not None:
            self._monitor.stop()
            self._monitor.join(timeout=max(1.0, self._monitor_interval * 5))
            self._monitor = None

    def __exit__(self, _, __, ___):
        self._stop_monitor()

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
        self._start_monitor()
        return self

    def __call__(self, stream_entries: List[Tuple[str, bytes]]):
        self._await_capacity()

        for stream_key, proto_data in stream_entries:
            self._add_to_stream(stream_key, proto_data)

        self._valkey_client.execute()
