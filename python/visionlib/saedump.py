from typing import Generator, List, TextIO

from pydantic import BaseModel

MESSAGE_SEPARATOR = ';'

def message_splitter(file: TextIO, chunk_size: int = 1 << 20) -> Generator[str, None, None]:
    '''Yield the messages of a saedump file, reading from the file's current position.

    Separators are only searched in newly read chunks, so the runtime is linear in the file size.
    Data after the last separator is not yielded.
    '''
    pending: List[str] = []
    while chunk := file.read(chunk_size):
        start = 0
        while (idx := chunk.find(MESSAGE_SEPARATOR, start)) != -1:
            pending.append(chunk[start:idx])
            yield ''.join(pending)
            pending = []
            start = idx + len(MESSAGE_SEPARATOR)
        if start < len(chunk):
            pending.append(chunk[start:])


class EventMeta(BaseModel):
    record_time: float
    source_stream: str
    
class Event(BaseModel):
    meta: EventMeta
    data_b64: str

class DumpMeta(BaseModel):
    start_time: float
    recorded_streams: List[str]
