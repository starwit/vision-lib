import io
import re
from typing import Generator, TextIO

import pytest

from visionlib.saedump import MESSAGE_SEPARATOR, message_splitter


def reference_message_splitter(file: TextIO) -> Generator[str, None, None]:
    '''The previous (quadratic) implementation, kept as the reference for the expected output.'''
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


@pytest.mark.parametrize('test_data', [
    ['test1', 'test2', 'test3'],
    ['test1'*1000, 'test2'*1000, 'test3', 'test4'*1000],
])
def test_message_splitter(test_data):
    test_file = io.StringIO(';'.join(test_data)+ ';')
    testee = message_splitter(test_file)
    messages = list(testee)
    assert messages == test_data


@pytest.mark.parametrize('content', [
    pytest.param('', id='empty'),
    pytest.param('a;', id='single'),
    pytest.param('a;b;', id='two'),
    pytest.param('a;b;trailing', id='trailing-data'),
    pytest.param(';;', id='empty-messages'),
    pytest.param(''.join(f'{{"msg": {i}}};' for i in range(10_000)), id='many'),
    pytest.param('x' * 5000 + ';' + 'y' * 3 + ';' + 'z' * 10_000 + ';', id='longer-than-chunk'),
    pytest.param('a;' + 'x' * ((1 << 20) * 3 // 2) + ';b;' + 'y' * 100, id='longer-than-default-chunk'),
])
@pytest.mark.parametrize('chunk_size', [1, 2, 3, None])
def test_message_splitter_matches_reference(content, chunk_size):
    expected = list(reference_message_splitter(io.StringIO(content)))
    kwargs = {} if chunk_size is None else {'chunk_size': chunk_size}
    assert list(message_splitter(io.StringIO(content), **kwargs)) == expected


def test_message_splitter_reads_from_current_position():
    test_file = io.StringIO('a;b;')
    assert list(message_splitter(test_file)) == ['a', 'b']
    test_file.seek(0)
    assert list(message_splitter(test_file)) == ['a', 'b']
