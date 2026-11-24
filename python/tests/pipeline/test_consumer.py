import base64
import logging
import threading
import time

import pytest

from visionlib.pipeline import ValkeyConsumer

logger = logging.getLogger(__name__)

def add_entry_async_delay(valkey_client, stream_key, payload, delay):
    def add_entry(valkey_client, stream_key, payload, delay):
        time.sleep(delay)
        valkey_client.xadd(stream_key, payload)
    threading.Thread(target=add_entry, args=(valkey_client, stream_key, payload, delay)).start()

def test_valkey_consumer(valkey_container, valkey_client):

    consumer = ValkeyConsumer(host=valkey_container.get_container_host_ip(),
                              port=valkey_container.get_exposed_port(6379),
                              stream_keys=['test_stream'],
                              block=500,
                              start_at_head=False)
    consumer.__enter__()
    consume = consumer()

    # Add test entry (needs to run in a thread, because the consumer will only read entries that are added while it blocks)
    add_entry_async_delay(valkey_client, 'test_stream', {'proto_data': b'hello1'}, 0.25)

    # Read test entry
    stream_key, payload = next(consume)
    assert stream_key == 'test_stream'
    assert payload == b'hello1'

    # Make sure we only read it once
    assert next(consume) == (None, None)

def test_valkey_consumer_existing(valkey_container, valkey_client):
    consumer = ValkeyConsumer(host=valkey_container.get_container_host_ip(),
                              port=valkey_container.get_exposed_port(6379),
                              stream_keys=['test_stream'],
                              block=500,
                              start_at_head=True)
    consumer.__enter__()
    consume = consumer()

    # Make sure stream is empty
    assert next(consume) == (None, None)

    # Add test entry
    valkey_client.xadd('test_stream', {'proto_data': b'hello1'})

    # Read test entry
    stream_key, payload = next(consume)
    assert stream_key == 'test_stream'
    assert payload == b'hello1'

    # Make sure we can only read it once (i.e. the stream pointer is moved forward)
    assert next(consume) == (None, None)

def test_valkey_consumer_detects_encoding(valkey_container, valkey_client):
    consumer = ValkeyConsumer(host=valkey_container.get_container_host_ip(),
                              port=valkey_container.get_exposed_port(6379),
                              stream_keys=['test_stream_mixed'],
                              block=500,
                              start_at_head=True)
    consumer.__enter__()
    consume = consumer()

    valkey_client.xadd('test_stream_mixed', {'proto_data': b'raw'})
    valkey_client.xadd('test_stream_mixed', {'proto_data_b64': base64.b64encode(b'encoded')})
    valkey_client.xadd('test_stream_mixed', {'unrelated': b'ignored'})
    valkey_client.xadd('test_stream_mixed', {'proto_data': b'after'})

    assert next(consume) == ('test_stream_mixed', b'raw')
    assert next(consume) == ('test_stream_mixed', b'encoded')
    # entry without payload field is skipped
    assert next(consume) == ('test_stream_mixed', b'after')
    assert next(consume) == (None, None)


@pytest.mark.parametrize('b64_decode', [True, False])
def test_valkey_consumer_b64_decode_deprecated(valkey_container, valkey_client, b64_decode):
    stream = f'test_stream_deprecated_{b64_decode}'
    with pytest.warns(DeprecationWarning, match='b64_decode'):
        consumer = ValkeyConsumer(host=valkey_container.get_container_host_ip(),
                                  port=valkey_container.get_exposed_port(6379),
                                  stream_keys=[stream],
                                  b64_decode=b64_decode,
                                  block=500,
                                  start_at_head=True)
    consumer.__enter__()
    consume = consumer()

    # the flag is ignored, both encodings are read regardless
    valkey_client.xadd(stream, {'proto_data': b'raw'})
    valkey_client.xadd(stream, {'proto_data_b64': base64.b64encode(b'encoded')})

    assert next(consume) == (stream, b'raw')
    assert next(consume) == (stream, b'encoded')
