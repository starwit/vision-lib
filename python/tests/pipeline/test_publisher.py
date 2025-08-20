import base64
import logging

from visionlib.pipeline.publisher import RedisPipelinePublisher, RedisPublisher

logger = logging.getLogger(__name__)

def test_redis_publisher(redis_container, redis_client):
    with RedisPublisher(host=redis_container.get_container_host_ip(), port=redis_container.get_exposed_port(6379), b64_encode=False) as publish:
        publish('test_stream', b'hello1')
        publish('test_stream', b'world1')

    stream = redis_client.xread({'test_stream': '0'}, count=5)
    assert len(stream) == 1
    assert len(stream[0]) == 2
    assert stream[0][1][0][1][b'proto_data'] == b'hello1'
    assert stream[0][1][1][1][b'proto_data'] == b'world1'

def test_redis_publisher_b64(redis_container, redis_client):
    with RedisPublisher(host=redis_container.get_container_host_ip(), port=redis_container.get_exposed_port(6379), b64_encode=True) as publish:
        publish('test_stream', b'hello2')
        publish('test_stream', b'world2')

    stream = redis_client.xread({'test_stream': '0'}, count=5)
    assert len(stream) == 1
    assert len(stream[0]) == 2
    assert base64.b64decode(stream[0][1][0][1][b'proto_data_b64']) == b'hello2'
    assert base64.b64decode(stream[0][1][1][1][b'proto_data_b64']) == b'world2'

def test_redis_pipeline_publisher(redis_container, redis_client):
    with RedisPipelinePublisher(host=redis_container.get_container_host_ip(), port=redis_container.get_exposed_port(6379), b64_encode=False) as publish:
        stream_entries = [
            ('test_stream', b'hello3'),
            ('test_stream', b'world3')
        ]
        publish(stream_entries)

    stream = redis_client.xread({'test_stream': '0'}, count=5)
    assert len(stream) == 1
    assert len(stream[0]) == 2
    assert stream[0][1][0][1][b'proto_data'] == b'hello3'
    assert stream[0][1][1][1][b'proto_data'] == b'world3'

def test_redis_pipeline_publisher_b64(redis_container, redis_client):
    with RedisPipelinePublisher(host=redis_container.get_container_host_ip(), port=redis_container.get_exposed_port(6379), b64_encode=True) as publish:
        stream_entries = [
            ('test_stream', b'hello4'),
            ('test_stream', b'world4')
        ]
        publish(stream_entries)

    stream = redis_client.xread({'test_stream': '0'}, count=5)
    assert len(stream) == 1
    assert len(stream[0]) == 2
    assert base64.b64decode(stream[0][1][0][1][b'proto_data_b64']) == b'hello4'
    assert base64.b64decode(stream[0][1][1][1][b'proto_data_b64']) == b'world4'