import logging
from collections import defaultdict
from typing import List, Tuple

import pybase64
import redis

logger = logging.getLogger(__name__)

class RedisConsumer:
    def __init__(self, host: str, port: int, stream_keys: List[str], b64_decode=True, block=2000) -> None:
        self._redis_client = None
        self._host = host
        self._port = port
        self._stream_keys = stream_keys
        self._b64_decode = b64_decode
        self._block = block

        self._last_retrieved_ids = defaultdict(lambda: '$')

    def __enter__(self):
        self._redis_client = redis.Redis(self._host, self._port)
        return self

    def __call__(self) -> Tuple[str, bytes]:
        data_field_name = b'proto_data_b64' if self._b64_decode else b'proto_data'

        while True:    
            result = self._redis_client.xread(
                count=1,
                block=self._block,
                streams={key: self._last_retrieved_ids[key] 
                            for key in self._stream_keys}
            )
            
            if result is None or len(result) == 0:
                yield None, None
                continue
            
            for item in result:
                proto_data = item[1][0][1][data_field_name]
                stream_key = item[0].decode('utf-8')

                self._last_retrieved_ids[stream_key] = item[1][0][0].decode('utf-8')

                if self._b64_decode:
                    yield stream_key, pybase64.b64decode(proto_data, validate=True)
                else:
                    yield stream_key, proto_data
        
    def __exit__(self, _, __, ___):
        try:
            self._redis_client.close()
        except Exception as e:
            logger.warn('Error while closing redis client', exc_info=e)
        
        return False
    