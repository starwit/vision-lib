import logging
import threading
import time

from prometheus_client import REGISTRY

from visionlib.pipeline import (DEFAULT_CONSUMER_GROUP, STREAM_LAG, ValkeyConsumer,
                                ValkeyPublisher)

logger = logging.getLogger(__name__)

STREAM = 'test_stream'
GROUP_BYTES = DEFAULT_CONSUMER_GROUP.encode('utf-8')


def _host_port(valkey_container):
    return valkey_container.get_container_host_ip(), valkey_container.get_exposed_port(6379)


def _wait_until(predicate, timeout=5.0, interval=0.02):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


def _lag_value(stream=STREAM):
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
        for i in range(3):
            publish(STREAM, f'm{i}'.encode())

        assert _wait_until(lambda: _lag_value() == 3)


def test_round_robin_two_backpressure_consumers(valkey_container, valkey_client):
    host, port = _host_port(valkey_container)

    with ValkeyPublisher(host=host, port=port, b64_encode=False, stream_maxlen=100) as publish:
        for i in range(10):
            publish(STREAM, f'm{i}'.encode())

    # TODO Do not use single letter variables (except trivial cases like loop var i)
    c1 = ValkeyConsumer(host=host, port=port, stream_keys=[STREAM], b64_decode=False,
                        block=200, enable_backpressure=True)
    c2 = ValkeyConsumer(host=host, port=port, stream_keys=[STREAM], b64_decode=False,
                        block=200, enable_backpressure=True)
    c1.__enter__()
    c2.__enter__()
    try:
        g1, g2 = c1(), c2()
        got1, got2 = [], []
        for _ in range(30):
            if len(got1) + len(got2) >= 10:
                break
            _, p1 = next(g1)
            if p1 is not None:
                got1.append(p1)
            _, p2 = next(g2)
            if p2 is not None:
                got2.append(p2)

        expected = {f'm{i}'.encode() for i in range(10)}
        assert set(got1).isdisjoint(got2)                 # round-robin: no message delivered twice
        assert set(got1) | set(got2) == expected          # together they got everything
        assert got1 and got2                              # both actually participated
    finally:
        c1.__exit__(None, None, None)
        c2.__exit__(None, None, None)


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
                return all(c['name'] != b'doomed' for c in consumers)

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
            gen = consumer()
            while not stop.is_set():
                _, p = next(gen)
                if p is not None:
                    received.append(p)
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
        gen = consumer()

        with ValkeyPublisher(host=host, port=port, b64_encode=False, stream_maxlen=100) as publish:
            assert publish._monitor is None            # backpressure off -> no monitor, no throttling
            for i in range(5):
                publish(STREAM, f'm{i}'.encode())

        received = []
        for _ in range(20):
            if len(received) == 5:
                break
            _, p = next(gen)
            if p is not None:
                received.append(p)

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
