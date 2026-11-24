import logging

import pytest
import valkey

from testcontainers.core.container import DockerContainer
from testcontainers.core.wait_strategies import LogMessageWaitStrategy

logger = logging.getLogger(__name__)

@pytest.fixture(scope='module')
def valkey_container():
    # Wait until Valkey accepts connections; otherwise the first test in a module can race the
    # server startup and fail with "Connection closed by server".
    container = (DockerContainer(image='valkey/valkey:9-alpine')
                 .with_exposed_ports(6379)
                 .waiting_for(LogMessageWaitStrategy('Ready to accept connections')))
    with container:
        yield container

@pytest.fixture(scope='module')
def valkey_client(valkey_container):
    return valkey.Valkey(host=valkey_container.get_container_host_ip(), port=valkey_container.get_exposed_port(6379))

@pytest.fixture(autouse=True)
def cleanup_valkey(valkey_client):
    yield
    valkey_client.flushall()