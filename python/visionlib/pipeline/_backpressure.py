'''Consumer-group / backpressure machinery, kept separate from the publisher and consumer types.

This module owns everything related to the default consumer group: the group name convention, the
Prometheus metrics, lag measurement, dead-consumer cleanup, the monitor thread, and the publisher-side
coordinators that decide whether publishing is throttled. It must not import ``publisher`` or
``consumer`` to avoid import cycles.
'''
import logging
import threading
import time
from typing import Callable, List, Optional

import valkey
from prometheus_client import Gauge

logger = logging.getLogger(__name__)

# Name of the consumer group that a backpressure-enabled publisher creates on every stream it owns.
# This is a hardcoded convention so that backpressure-aware consumers can attach without extra configuration.
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


def ensure_group(client: valkey.Valkey, stream_key: str, group: str, id: str = '$') -> None:
    '''Create the consumer group on a stream, tolerating an already-existing group.'''
    try:
        client.xgroup_create(stream_key, group, id=id, mkstream=True)
    except valkey.exceptions.ResponseError as e:
        if 'BUSYGROUP' not in str(e):
            raise


def measure_lag(client: valkey.Valkey, stream_key: str, group: str) -> int:
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


class GroupMonitor(threading.Thread):
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
            lag = measure_lag(self._client, stream_key, self._group)
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

    def _should_fail_open(self, all_below_threshold: bool, total_live_consumers: int) -> bool:
        '''Release the publisher if it would otherwise block forever with no live consumer left.

        The publisher recovers automatically: as soon as a live consumer reappears (or lag drops on
        its own) the timer resets and normal lag-based gating resumes.
        '''
        blocking = not all_below_threshold
        if self._fail_open_timeout is None or not blocking or total_live_consumers > 0:
            # Strict mode, not blocking, or someone is still consuming: reset the timer.
            if self._fail_open_logged:
                logger.info('Backpressure: live consumers returned, resuming normal throttling')
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


class NoopCoordinator:
    '''Coordinator for a publisher that does not honour backpressure: every hook is a no-op.

    Such a publisher leaves the stream alone (no consumer group, no monitor, no throttling), so a
    backpressure consumer attaching later creates the group itself and its ``start_at_head`` applies.
    '''

    def start(self) -> None:
        pass

    def ensure_stream(self, stream_key: str) -> None:
        pass

    def await_capacity(self) -> None:
        pass

    def stop(self) -> None:
        pass


class BackpressureCoordinator(NoopCoordinator):
    '''Owns the default consumer group on the streams a publisher writes to and throttles publishing
    to keep the group's lag in check.

    The group is created on each stream the first time it is published to. A GroupMonitor runs out
    of band; it flips a threading.Event that await_capacity() blocks on, so the publishing thread
    slows down whenever the consumer group falls behind.
    '''

    def __init__(self, admin_client: valkey.Valkey, threshold: int, monitor_interval: float,
                 consumer_idle_timeout_ms: int, fail_open_timeout: Optional[float],
                 group: str = DEFAULT_CONSUMER_GROUP) -> None:
        self._admin_client = admin_client
        self._group = group
        self._known_streams = set()
        self._streams_lock = threading.Lock()
        self._monitor_interval = monitor_interval
        # Set == the publisher may write. Initially open; the monitor clears it when lag is too high.
        self._ok_to_publish = threading.Event()
        self._ok_to_publish.set()
        self._monitor = GroupMonitor(
            client=admin_client,
            group=group,
            get_streams=self.registered_streams,
            threshold=threshold,
            idle_timeout_ms=consumer_idle_timeout_ms,
            interval=monitor_interval,
            fail_open_timeout=fail_open_timeout,
            ok_event=self._ok_to_publish,
        )

    def ensure_stream(self, stream_key: str) -> None:
        '''Create the group on a stream the first time we publish to it (idempotent, cached).'''
        with self._streams_lock:
            if stream_key in self._known_streams:
                return
        ensure_group(self._admin_client, stream_key, self._group, id='$')
        with self._streams_lock:
            self._known_streams.add(stream_key)

    def registered_streams(self) -> List[str]:
        with self._streams_lock:
            return list(self._known_streams)

    def start(self) -> None:
        self._monitor.start()

    def await_capacity(self) -> None:
        self._ok_to_publish.wait()

    def stop(self) -> None:
        self._monitor.stop()
        self._monitor.join(timeout=max(1.0, self._monitor_interval * 5))
