import logging

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