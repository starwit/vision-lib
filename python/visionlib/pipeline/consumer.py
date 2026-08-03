import logging
import os
import socket
import uuid
from typing import Generator, List, Optional, Tuple

import pybase64
import valkey

from ._backpressure import DEFAULT_CONSUMER_GROUP, ensure_group

logger = logging.getLogger(__name__)


class _PlainReader:
    '''Reads with XREAD and manual per-stream offsets: fan-out, every consumer sees every message.'''

    def __init__(self, stream_keys: List[str], block: int, start_at_head: bool) -> None:
        self._block = block
        init_stream_pointer = '$' if not start_at_head else '0'
        self._stream_pointers = {key: init_stream_pointer for key in stream_keys}

    def setup(self, client: valkey.Valkey) -> None:
        pass

    def messages(self, client: valkey.Valkey, data_field_name: bytes) -> Generator[Tuple, None, None]:
        while True:
            result = client.xread(count=1, block=self._block, streams=self._stream_pointers)

            if result is None or len(result) == 0:
                yield None, None
                continue

            for item in result:
                proto_data = item[1][0][1][data_field_name]
                stream_key = item[0].decode('utf-8')
                self._update_stream_pointers(stream_key, retrieved_id=item[1][0][0].decode('utf-8'))
                yield stream_key, proto_data

    def _update_stream_pointers(self, stream_key: str, retrieved_id: str) -> None:
        self._stream_pointers[stream_key] = retrieved_id

        # should only happen on the first ever received message: move all stream pointers away from '$'
        if '$' in self._stream_pointers.values():
            for key in self._stream_pointers:
                if self._stream_pointers[key] == '$':
                    self._stream_pointers[key] = retrieved_id


class _GroupReader:
    '''Reads with XREADGROUP (NOACK) as part of the shared consumer group.

    Attaching to the group is what lets the publisher sense how far behind this consumer is (its lag),
    which is what "participating in backpressure" means. NOACK: entries are delivered but never
    tracked in a pending list, so the group's read position advances on delivery and there is nothing
    to acknowledge. A message in flight when this consumer crashes is not redelivered.

    Note: run a single consumer per group for now. A group can technically distribute entries across
    several consumers, but that reorders the stream, so it is not a supported mode yet.
    '''

    def __init__(self, stream_keys: List[str], block: int, start_at_head: bool,
                 consumer_name: str, group: str = DEFAULT_CONSUMER_GROUP) -> None:
        self._stream_keys = stream_keys
        self._block = block
        self._start_at_head = start_at_head
        self._consumer_name = consumer_name
        self._group = group
        self._streams = {key: '>' for key in stream_keys}

    def setup(self, client: valkey.Valkey) -> None:
        # The publisher normally owns and creates the group, but we create it here too so that a
        # backpressure consumer also works against an old publisher that never created one.
        # start_at_head only takes effect when *this* consumer creates the group; against an existing
        # group the read position is server-side and shared.
        group_id = '0' if self._start_at_head else '$'
        for stream_key in self._stream_keys:
            ensure_group(client, stream_key, self._group, id=group_id)

    def messages(self, client: valkey.Valkey, data_field_name: bytes) -> Generator[Tuple, None, None]:
        while True:
            result = client.xreadgroup(self._group, self._consumer_name, count=1, block=self._block,
                                       streams=self._streams, noack=True)

            if result is None or len(result) == 0:
                yield None, None
                continue

            for item in result:
                entries = item[1]
                if not entries:
                    continue
                proto_data = entries[0][1][data_field_name]
                stream_key = item[0].decode('utf-8')
                yield stream_key, proto_data


class ValkeyConsumer:
    def __init__(self, host: str, port: int, stream_keys: List[str], b64_decode: bool = True,
                 block: int = 2000, start_at_head: bool = False, enable_backpressure: bool = False,
                 consumer_name: Optional[str] = None) -> None:
        self._valkey_client = None
        self._host = host
        self._port = port
        self._b64_decode = b64_decode

        # The read behavior is chosen once here. When backpressure is enabled the consumer attaches to
        # the shared consumer group (for lag tracking); otherwise it does plain fan-out reads.
        self._reader = self._build_reader(enable_backpressure, list(stream_keys), block,
                                          start_at_head, consumer_name)

    def _build_reader(self, enable_backpressure: bool, stream_keys: List[str], block: int,
                      start_at_head: bool, consumer_name: Optional[str]):
        if enable_backpressure:
            name = consumer_name or f'{socket.gethostname()}-{os.getpid()}-{uuid.uuid4().hex[:8]}'
            return _GroupReader(stream_keys, block, start_at_head, name)
        return _PlainReader(stream_keys, block, start_at_head)

    def __enter__(self):
        self._valkey_client = valkey.Valkey(self._host, self._port)
        self._reader.setup(self._valkey_client)
        return self

    def __call__(self) -> Generator[Tuple[str, bytes], None, None]:
        data_field_name = b'proto_data_b64' if self._b64_decode else b'proto_data'

        for stream_key, proto_data in self._reader.messages(self._valkey_client, data_field_name):
            if stream_key is None:
                yield None, None
            elif self._b64_decode:
                yield stream_key, pybase64.b64decode(proto_data, validate=True)
            else:
                yield stream_key, proto_data

    def __exit__(self, _, __, ___):
        try:
            self._valkey_client.close()
        except Exception as e:
            logger.warning('Error while closing valkey client', exc_info=e)

        return False
