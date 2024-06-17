from typing import Generator, List, TextIO

from pydantic import BaseModel

MESSAGE_SEPARATOR = ';'

def message_splitter(file: TextIO) -> Generator[str, None, None]:
    buffer = ''
    while True:
        chunk = file.read(4096)
        if len(chunk) == 0:
            break
        buffer += chunk
        sep_idx = buffer.find(MESSAGE_SEPARATOR)
        if sep_idx != -1:
            yield buffer[:sep_idx]
            buffer = buffer[sep_idx+1:]


class EventMeta(BaseModel):
    record_time: float
    source_stream: str
    
class Event(BaseModel):
    meta: EventMeta
    data_b64: str

class DumpMeta(BaseModel):
    start_time: float
    recorded_streams: List[str]
