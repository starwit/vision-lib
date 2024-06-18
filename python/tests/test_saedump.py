import io
from visionlib.saedump import message_splitter
import pytest

@pytest.mark.parametrize('test_data', [
    ['test1', 'test2', 'test3'],
    ['test1'*1000, 'test2'*1000, 'test3', 'test4'*1000],
])
def test_message_splitter(test_data):
    test_file = io.StringIO(';'.join(test_data)+ ';')
    testee = message_splitter(test_file)
    messages = list(testee)
    assert messages == test_data