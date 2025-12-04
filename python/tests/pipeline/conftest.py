import logging

import pytest
import valkey
from testcontainers.redis import RedisContainer

logger = logging.getLogger(__name__)

@pytest.fixture(scope='module')
def valkey_container():
    with RedisContainer(image='valkey/valkey:9-alpine') as container:
        yield container

@pytest.fixture(scope='module')
def valkey_client(valkey_container):
    return valkey.Valkey(host=valkey_container.get_container_host_ip(), port=valkey_container.get_exposed_port(6379))

@pytest.fixture(autouse=True)
def cleanup_valkey(valkey_client):
    yield
    valkey_client.flushall()