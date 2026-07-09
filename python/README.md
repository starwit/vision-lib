# vision-lib (Python)

Common components for building [Starwit Awareness Engine](https://github.com/starwit/starwit-awareness-engine) (SAE) stages in Python. See the [repository overview](../README.md) for the bigger picture.

## Installation

The package is not published to PyPI; install it directly from the Git repository, pinned to a [release tag](https://github.com/starwit/vision-lib/tags).

```bash
poetry add git+https://github.com/starwit/vision-lib.git@1.0.1#subdirectory=python
# or
pip install "git+https://github.com/starwit/vision-lib.git@1.0.1#subdirectory=python"
```

## What's available

- **[`visionlib.pipeline`](visionlib/pipeline/__init__.py)** – move `SaeMessage` protobufs through Valkey streams:
  - [`ValkeyConsumer`](visionlib/pipeline/consumer.py) – read messages from one or more streams.
  - [`ValkeyPublisher`](visionlib/pipeline/publisher.py) – write messages to a stream; `ValkeyPipelinePublisher` batches writes into one round-trip.
  - [`get_raw_frame_data`](visionlib/pipeline/tools.py) – extract a video frame as a numpy array (JPEG decoded transparently).
  - [`formats`](visionlib/pipeline/formats.py) – validate `SaeMessage` / `PositionMessage` objects.
  - [`settings`](visionlib/pipeline/settings.py) – YAML config source and log-level enum for `pydantic-settings`.
- **[`visionlib.saedump`](visionlib/saedump.py)** – read `.saedump` recordings (see the [format specification](../doc/saedump-format.md)).

## Development

### Running tests

Activate the environment and run `pytest`. Tests spin up a Valkey instance via [testcontainers](https://testcontainers-python.readthedocs.io/), so a working Docker installation is required.

If you see weird docker errors, it is probably because you are running rootless Docker
(see [this issue](https://github.com/testcontainers/testcontainers-python/issues/537)).
Make sure `DOCKER_HOST` points at the correct socket:

```bash
export DOCKER_HOST=unix:///run/user/$(id -u)/docker.sock
```

## Changelog

### 1.0.1
- Restrict pyturbojpeg to 1.x (2.x requires libjpeg-turbo 3.x, which is not available on Ubuntu 24.04 LTS)

### 1.0.0
- Migrate from redis-py to valkey-py
  - Use `valkey-py>=6.1.1`
  - Breaks compatibility: imports and constructor calls for consumer and publisher must be changed!
- Provide cleaner imports (`from visionlib.pipeline import ValkeyConsumer`)
