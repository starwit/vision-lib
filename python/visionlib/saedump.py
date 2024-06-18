import re
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
        prev_end = 0
        for match in re.finditer(rf'{MESSAGE_SEPARATOR}', buffer):
            yield buffer[prev_end:match.start()]
            prev_end = match.end()
        buffer = buffer[prev_end:]


class EventMeta(BaseModel):
    record_time: float
    source_stream: str
    
class Event(BaseModel):
    meta: EventMeta
    data_b64: str

class DumpMeta(BaseModel):
    start_time: float
    recorded_streams: List[str]
