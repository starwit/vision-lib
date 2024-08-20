# Python version of vision-lib

## How to run tests
Activate the environment and run `pytest`.
If you see weird docker errors, that is probably because you're running rootless docker.
(see https://github.com/testcontainers/testcontainers-python/issues/537)
There are two solutions to this:
- Pass the correct Docker socket to testcontainers (it apparently cannot pick that up automatically yet) by setting `TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE=/run/user/$(id -u)/docker.sock`
- Disable Ryuk (which reaps Docker resources after the test; not recommended to disable) by setting `TESTCONTAINERS_RYUK_DISABLED=true`