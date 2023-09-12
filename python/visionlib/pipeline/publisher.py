import redis

class RedisPublisher:
    def __init__(self, host: str, port: int, stream_maxlen=10) -> None:
        self._redis_client = redis.Redis(host, port)
        self._host = host
        self._port = port
        self._stream_maxlen = 10

    def __call__(self, stream_key: str, proto_data_b64: str):
        self._redis_client.xadd(
            name=stream_key, 
            fields={'proto_data_b64': proto_data_b64}, 
            maxlen=self._stream_maxlen
        )