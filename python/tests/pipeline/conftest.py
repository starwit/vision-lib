import logging

import pytest
import redis
from testcontainers.redis import RedisContainer

logger = logging.getLogger(__name__)

@pytest.fixture(scope='module')
def redis_container():
    with RedisContainer() as container:
        yield container

@pytest.fixture(scope='module')
def redis_client(redis_container):
    return redis.Redis(host=redis_container.get_container_host_ip(), port=redis_container.get_exposed_port(6379))

@pytest.fixture(autouse=True)
def cleanup_redis(redis_client):
    yield
    redis_client.flushall()