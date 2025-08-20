import logging
from typing import Generator, List, Tuple

import pybase64
import redis

logger = logging.getLogger(__name__)

class RedisConsumer:
    def __init__(self, host: str, port: int, stream_keys: List[str], b64_decode=True, block=2000, read_existing_entries: bool = False) -> None:
        self._redis_client = None
        self._host = host
        self._port = port
        self._b64_decode = b64_decode
        self._block = block
        self._read_existing_entries = read_existing_entries

        init_stream_pointer = '$' if not read_existing_entries else '0'
        self._stream_pointers = {key: init_stream_pointer for key in stream_keys}

    def __enter__(self):
        self._redis_client = redis.Redis(self._host, self._port)
        return self

    def __call__(self) -> Generator[Tuple[str, bytes], None, None]:
        data_field_name = b'proto_data_b64' if self._b64_decode else b'proto_data'

        while True:    
            result = self._redis_client.xread(
                count=1,
                block=self._block,
                streams=self._stream_pointers
            )
            
            if result is None or len(result) == 0:
                yield None, None
                continue
            
            for item in result:
                proto_data = item[1][0][1][data_field_name]
                stream_key = item[0].decode('utf-8')

                self._update_stream_pointers(stream_key, retrieved_id=item[1][0][0].decode('utf-8'))

                if self._b64_decode:
                    yield stream_key, pybase64.b64decode(proto_data, validate=True)
                else:
                    yield stream_key, proto_data

    def _update_stream_pointers(self, stream_key, retrieved_id):
        self._stream_pointers[stream_key] = retrieved_id

        # should only happen on the first ever received message: move all stream pointers away from '$'
        if '$' in self._stream_pointers.values():
            for key in self._stream_pointers:
                if self._stream_pointers[key] == '$':
                    self._stream_pointers[key] = retrieved_id
        
    def __exit__(self, _, __, ___):
        try:
            self._redis_client.close()
        except Exception as e:
            logger.warn('Error while closing redis client', exc_info=e)
        
        return False