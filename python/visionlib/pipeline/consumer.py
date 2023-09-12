import redis
from typing import List
from collections import defaultdict

class RedisConsumer:
    def __init__(self, host: str, port: int, stream_keys: List[str]) -> None:
        self._redis_client = redis.Redis(host, port)
        self._stream_keys = stream_keys

        self._last_retrieved_ids = defaultdict(lambda: '$')
        
        self._generating = False

    def __call__(self):
        self._generating = True

        while self._generating:
            result = self._redis_client.xread(
                count=1,
                block=2000,
                streams={key: self._last_retrieved_ids[key] 
                            for key in self._stream_keys}
            )
            
            if result is None:
                yield None
            
            for item in result:
                proto_b64 = item[1][0][1][b'proto_data_b64']
                stream_key = item[0].decode('utf-8')

                self._last_retrieved_ids[stream_key] = item[1][0][0].decode('utf-8')

                yield proto_b64
        
        self._redis_client.close()
    
    def stop(self):
        self._generating = False
