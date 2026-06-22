# Python version of vision-lib

## How to run tests
Activate the environment and run `pytest`.
If you see weird docker errors, that is probably because you're running rootless docker.
(see https://github.com/testcontainers/testcontainers-python/issues/537)
The solution to this is to make sure that `DOCKER_HOST` points at the correct docker socket, i.e.:\
`export DOCKER_HOST=unix:///run/user/$(id -u)/docker.sock`

## Changelog
### 1.0.1
- Restrict pyturbojpeg to 1.x (2.x requires libjpeg-turbo 3.x, which is not avaiable on Ubuntu 24.04 LTS)

### 1.0.0
- Migrate from redis-py to valkey-py
  - Use `valkey-py>=6.1.1`
  - Breaks compatibility: imports and constructor calls for consumer and publisher must be changed!
- Provide cleaner imports (`from visionlib.pipeline import ValkeyConsumer`)