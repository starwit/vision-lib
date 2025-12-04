import logging

import pytest
import valkey

from testcontainers.core.container import DockerContainer

logger = logging.getLogger(__name__)

@pytest.fixture(scope='module')
def valkey_container():
    with DockerContainer(image='valkey/valkey:9-alpine').with_exposed_ports(6379) as container:
        yield container

@pytest.fixture(scope='module')
def valkey_client(valkey_container):
    return valkey.Valkey(host=valkey_container.get_container_host_ip(), port=valkey_container.get_exposed_port(6379))

@pytest.fixture(autouse=True)
def cleanup_valkey(valkey_client):
    yield
    valkey_client.flushall()