import logging
import threading
import time

from visionlib.pipeline.consumer import RedisConsumer

logger = logging.getLogger(__name__)

def add_entry_async_delay(redis_client, stream_key, payload, delay):
    def add_entry(redis_client, stream_key, payload, delay):
        time.sleep(delay)
        redis_client.xadd(stream_key, payload)
    threading.Thread(target=add_entry, args=(redis_client, stream_key, payload, delay)).start()

def test_redis_consumer(redis_container, redis_client):

    consumer = RedisConsumer(host=redis_container.get_container_host_ip(),
                             port=redis_container.get_exposed_port(6379),
                             stream_keys=['test_stream'],
                             b64_decode=False, 
                             block=500,
                             start_at_head=False)
    consumer.__enter__()
    consume = consumer()

    # Add test entry (needs to run in a thread, because the consumer will only read entries that are added while it blocks)
    add_entry_async_delay(redis_client, 'test_stream', {'proto_data': b'hello1'}, 0.25)

    # Read test entry
    stream_key, payload = next(consume)
    assert stream_key == 'test_stream'
    assert payload == b'hello1'

    # Make sure we only read it once
    assert next(consume) == (None, None)

def test_redis_consumer_existing(redis_container, redis_client):
    consumer = RedisConsumer(host=redis_container.get_container_host_ip(),
                             port=redis_container.get_exposed_port(6379),
                             stream_keys=['test_stream'],
                             b64_decode=False, 
                             block=500,
                             start_at_head=True)
    consumer.__enter__()
    consume = consumer()

    # Make sure stream is empty
    assert next(consume) == (None, None)

    # Add test entry
    redis_client.xadd('test_stream', {'proto_data': b'hello1'})

    # Read test entry
    stream_key, payload = next(consume)
    assert stream_key == 'test_stream'
    assert payload == b'hello1'

    # Make sure we can only read it once (i.e. the stream pointer is moved forward)
    assert next(consume) == (None, None)