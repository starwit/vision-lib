import logging
import threading
import time
from typing import Callable

from prometheus_client import REGISTRY

from visionlib.pipeline import ValkeyConsumer, ValkeyPublisher
# These are internal implementation details, imported directly (not re-exported by the package).
from visionlib.pipeline._backpressure import (DEFAULT_CONSUMER_GROUP, STREAM_LAG,
                                              BackpressureCoordinator, GroupCoordinator, GroupMonitor)

logger = logging.getLogger(__name__)

STREAM = 'test_stream'
GROUP_BYTES = DEFAULT_CONSUMER_GROUP.encode('utf-8')


def _host_port(valkey_container):
    return valkey_container.get_container_host_ip(), valkey_container.get_exposed_port(6379)


def _wait_until(predicate: Callable[[], bool], timeout: float = 5.0, interval: float = 0.02) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


def _lag_value(stream: str = STREAM):
    return REGISTRY.get_sample_value('visionlib_stream_consumer_group_lag',
                                     {'stream': stream, 'group': DEFAULT_CONSUMER_GROUP})


# --- Group / metric / lifecycle -------------------------------------------------------------

def test_publisher_creates_group(valkey_container, valkey_client):
    host, port = _host_port(valkey_container)
    with ValkeyPublisher(host=host, port=port, b64_encode=False) as publish:
        publish(STREAM, b'hello')

    groups = valkey_client.xinfo_groups(STREAM)
    assert len(groups) == 1
    assert groups[0]['name'] == GROUP_BYTES


def test_group_creation_is_idempotent(valkey_container, valkey_client):
    host, port = _host_port(valkey_container)
    for payload in (b'a', b'b'):
        with ValkeyPublisher(host=host, port=port, b64_encode=False) as publish:
            publish(STREAM, payload)

    groups = valkey_client.xinfo_groups(STREAM)
    assert len(groups) == 1


def test_lag_gauge_reflects_pending(valkey_container, valkey_client):
    host, port = _host_port(valkey_container)
    STREAM_LAG.clear()

    # Threshold defaults to stream_maxlen // 2 == 5, so publishing 3 stays below and never blocks.
    with ValkeyPublisher(host=host, port=port, b64_encode=False, stream_maxlen=10,
                         enable_backpressure=True, monitor_interval=0.02) as publish:
        assert type(publish._coordinator) is BackpressureCoordinator   # backpressure on -> monitor runs
        for i in range(3):
            publish(STREAM, f'm{i}'.encode())

        assert _wait_until(lambda: _lag_value() == 3)


def test_round_robin_two_backpressure_consumers(valkey_container, valkey_client):
    host, port = _host_port(valkey_container)

    with ValkeyPublisher(host=host, port=port, b64_encode=False, stream_maxlen=100) as publish:
        for i in range(10):
            publish(STREAM, f'm{i}'.encode())

    first_consumer = ValkeyConsumer(host=host, port=port, stream_keys=[STREAM], b64_decode=False,
                                    block=200, enable_backpressure=True)
    second_consumer = ValkeyConsumer(host=host, port=port, stream_keys=[STREAM], b64_decode=False,
                                     block=200, enable_backpressure=True)
    first_consumer.__enter__()
    second_consumer.__enter__()
    try:
        first_messages, second_messages = first_consumer(), second_consumer()
        received_first, received_second = [], []
        for _ in range(30):
            if len(received_first) + len(received_second) >= 10:
                break
            _, first_payload = next(first_messages)
            if first_payload is not None:
                received_first.append(first_payload)
            _, second_payload = next(second_messages)
            if second_payload is not None:
                received_second.append(second_payload)

        expected = {f'm{i}'.encode() for i in range(10)}
        assert set(received_first).isdisjoint(received_second)   # round-robin: no message delivered twice
        assert set(received_first) | set(received_second) == expected   # together they got everything
        assert received_first and received_second                # both actually participated
    finally:
        first_consumer.__exit__(None, None, None)
        second_consumer.__exit__(None, None, None)


def test_dead_consumer_cleanup(valkey_container, valkey_client):
    host, port = _host_port(valkey_container)

    with ValkeyPublisher(host=host, port=port, b64_encode=False, stream_maxlen=100,
                         enable_backpressure=True, monitor_interval=0.05,
                         consumer_idle_timeout_ms=300, fail_open_timeout=None) as publish:
        consumer = ValkeyConsumer(host=host, port=port, stream_keys=[STREAM], b64_decode=False,
                                  block=200, enable_backpressure=True, consumer_name='doomed')
        consumer.__enter__()
        try:
            publish(STREAM, b'hello')
            _, payload = next(consumer())
            assert payload == b'hello'

            # The consumer is now idle; the monitor must eventually DELCONSUMER it.
            def consumer_gone():
                consumers = valkey_client.xinfo_consumers(STREAM, DEFAULT_CONSUMER_GROUP)
                return all(consumer_info['name'] != b'doomed' for consumer_info in consumers)

            assert _wait_until(consumer_gone, timeout=5)
        finally:
            consumer.__exit__(None, None, None)


# --- The four publisher x consumer backpressure combinations ---------------------------------

def test_both_on_throttles_and_delivers_all(valkey_container, valkey_client):
    '''(publisher on, consumer on): a fast producer is throttled so nothing is dropped even though
    the stream is trimmed to hold far fewer entries than the total that flows through it.'''
    host, port = _host_port(valkey_container)

    total = 200
    received = []
    stop = threading.Event()

    def consume():
        consumer = ValkeyConsumer(host=host, port=port, stream_keys=[STREAM], b64_decode=False,
                                  block=200, enable_backpressure=True)
        consumer.__enter__()
        try:
            messages = consumer()
            while not stop.is_set():
                _, payload = next(messages)
                if payload is not None:
                    received.append(payload)
                    time.sleep(0.008)   # deliberately slower than the producer
        finally:
            consumer.__exit__(None, None, None)

    published = []

    def produce():
        with ValkeyPublisher(host=host, port=port, b64_encode=False, stream_maxlen=30,
                             enable_backpressure=True, backpressure_threshold=10,
                             monitor_interval=0.02, fail_open_timeout=None) as publish:
            for i in range(total):
                publish(STREAM, f'm{i}'.encode())
                published.append(i)
                time.sleep(0.002)

    consumer_thread = threading.Thread(target=consume)
    producer_thread = threading.Thread(target=produce)
    consumer_thread.start()
    producer_thread.start()

    producer_thread.join(timeout=40)
    assert not producer_thread.is_alive()
    assert len(published) == total

    assert _wait_until(lambda: len(received) >= total, timeout=20)
    stop.set()
    consumer_thread.join(timeout=5)

    expected = {f'm{i}'.encode() for i in range(total)}
    assert set(received) == expected                        # nothing dropped...
    assert valkey_client.xlen(STREAM) < total               # ...even though the stream was trimmed
                                                            # to hold far fewer than the 200 total


def test_pub_on_consumer_off_fails_open(valkey_container, valkey_client, caplog):
    '''(publisher on, consumer off): with no consumer ever joining the group, lag never drains, so
    the publisher would block forever. The fail-open safeguard must release it.'''
    host, port = _host_port(valkey_container)

    published = []

    def produce():
        with ValkeyPublisher(host=host, port=port, b64_encode=False, stream_maxlen=10,
                             enable_backpressure=True, backpressure_threshold=5,
                             monitor_interval=0.05, fail_open_timeout=0.5) as publish:
            for i in range(30):
                publish(STREAM, f'm{i}'.encode())
                published.append(i)
                time.sleep(0.02)   # keep the producer running long enough for backpressure to engage

    with caplog.at_level(logging.WARNING):
        producer_thread = threading.Thread(target=produce)
        producer_thread.start()
        producer_thread.join(timeout=15)

    assert not producer_thread.is_alive()      # fail-open released it instead of blocking forever
    assert len(published) == 30
    assert 'no live consumers' in caplog.text


def test_pub_off_consumer_on_no_throttle(valkey_container, valkey_client):
    '''(publisher off, consumer on): the publisher does plain fire-and-forget XADD (no monitor, no
    blocking), but a backpressure consumer still attaches to the group and receives everything.'''
    host, port = _host_port(valkey_container)

    consumer = ValkeyConsumer(host=host, port=port, stream_keys=[STREAM], b64_decode=False,
                              block=200, enable_backpressure=True)
    consumer.__enter__()
    try:
        messages = consumer()

        with ValkeyPublisher(host=host, port=port, b64_encode=False, stream_maxlen=100) as publish:
            # Backpressure off -> the passive coordinator (no monitor, no throttling).
            assert type(publish._coordinator) is GroupCoordinator
            for i in range(5):
                publish(STREAM, f'm{i}'.encode())

        received = []
        for _ in range(20):
            if len(received) == 5:
                break
            _, payload = next(messages)
            if payload is not None:
                received.append(payload)

        assert set(received) == {f'm{i}'.encode() for i in range(5)}
    finally:
        consumer.__exit__(None, None, None)


def test_both_off_is_legacy_xread(valkey_container, valkey_client):
    '''(publisher off, consumer off): default path is byte-for-byte the old wire format, readable by
    a plain XREAD consumer.'''
    host, port = _host_port(valkey_container)

    with ValkeyPublisher(host=host, port=port, b64_encode=False) as publish:
        publish(STREAM, b'hello')
        publish(STREAM, b'world')

    stream = valkey_client.xread({STREAM: '0'}, count=5)
    assert stream[0][1][0][1][b'proto_data'] == b'hello'
    assert stream[0][1][1][1][b'proto_data'] == b'world'


# --- Fail-open state machine (no Valkey needed) ----------------------------------------------

def test_fail_open_recovers_when_consumer_returns():
    '''The publisher does recover from the fail-open state: once a live consumer reappears, normal
    lag-based throttling resumes, and it can fail open again on a later outage.'''
    fail_open_timeout = 0.1
    monitor = GroupMonitor(client=None, group=DEFAULT_CONSUMER_GROUP, get_streams=lambda: [],
                           threshold=5, idle_timeout_ms=1000, interval=0.05,
                           fail_open_timeout=fail_open_timeout, ok_event=threading.Event())

    # Blocking (lag high) with no live consumers, before the timeout elapses -> keep holding.
    assert monitor._should_fail_open(all_below_threshold=False, total_live_consumers=0) is False
    time.sleep(fail_open_timeout + 0.05)
    # Timeout elapsed with still no consumers -> fail open (release the publisher).
    assert monitor._should_fail_open(all_below_threshold=False, total_live_consumers=0) is True
    # A live consumer returns -> recover, resume normal gating even though lag is still high.
    assert monitor._should_fail_open(all_below_threshold=False, total_live_consumers=1) is False

    # And it can fail open again if the consumers disappear once more.
    assert monitor._should_fail_open(all_below_threshold=False, total_live_consumers=0) is False
    time.sleep(fail_open_timeout + 0.05)
    assert monitor._should_fail_open(all_below_threshold=False, total_live_consumers=0) is True
