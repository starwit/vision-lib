import logging
from typing import List, Tuple

import pybase64
import redis

logger = logging.getLogger(__name__)

class RedisPublisher:
    def __init__(self, host: str, port: int, stream_maxlen=10, b64_encode=True, **redis_args) -> None:
        self._redis_client = None
        self._redis_args = redis_args
        self._host = host
        self._port = port
        self._stream_maxlen = stream_maxlen
        self._b64_encode = b64_encode

    def __enter__(self):
        self._redis_client = redis.Redis(self._host, self._port, **self._redis_args)
        return self

    def __call__(self, stream_key: str, proto_data: bytes):
        self._add_to_stream(stream_key, proto_data)

    def _add_to_stream(self, stream_key: str, proto_data: bytes):
        data_field_name = 'proto_data'
        data_field_value = proto_data

        if self._b64_encode:
            data_field_name = 'proto_data_b64'
            data_field_value = pybase64.b64encode(proto_data)

        self._redis_client.xadd(
            name=stream_key, 
            fields={data_field_name: data_field_value}, 
            maxlen=self._stream_maxlen
        )
    
    def __exit__(self, _, __, ___):
        try:
            self._redis_client.close()
        except Exception as e:
            logger.warn('Error while closing redis client', exc_info=e)
        
        return False
    
class RedisPipelinePublisher(RedisPublisher):
    '''A version of the redis publisher that uses pipelining to make the sending process more efficient.'''
    def __init__(self, host: str, port: int, stream_maxlen=10, b64_encode=True, **redis_args) -> None:
        super().__init__(host, port, stream_maxlen, b64_encode, **redis_args)

    def __enter__(self):
        # This works because Pipeline is a subclass of Redis
        self._redis_client = redis.Redis(self._host, self._port, **self._redis_args).pipeline(transaction=False)
        return self
    
    def __call__(self, stream_entries: List[Tuple[str, bytes]]):
        for stream_key, proto_data in stream_entries:
            self._add_to_stream(stream_key, proto_data)

        self._redis_client.execute()
