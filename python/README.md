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

### Backpressure (optional)

By default the publisher is **fire-and-forget**: if a consumer can't keep up, older messages are trimmed away (`stream_maxlen` bounds memory usage). This is the right trade-off for real-time video.

For batch/replay use cases where **no message may be dropped**, set `enable_backpressure=True` on *both* ends. The publisher then slows down to keep the consumer group's lag below a threshold, and the consumer attaches to a shared group so its lag can be tracked:

```python
with ValkeyPublisher(host, port, stream_maxlen=1000, enable_backpressure=True) as publish:
    publish('mystream', proto_bytes)   # blocks while the consumer group is too far behind

consumer = ValkeyConsumer(host, port, ['mystream'], enable_backpressure=True)
```

Notes:
- Use a single (backpressure-enabled) consumer per stream for now. A consumer group can technically spread messages across several consumers, but that reorders the stream, so it is not a supported mode yet.
- Opt-in and off by default; the wire protocol is unchanged, so new and old publishers/consumers still interoperate (just without the new behavior).
- The publisher exports the monitored lag as a Prometheus gauge (`visionlib_stream_consumer_group_lag`).
- If no consumer stays alive, the publisher *fails open* after `fail_open_timeout` seconds (resuming, and dropping again) rather than blocking forever.

See [how backpressure works](../doc/backpressure.md) for the conceptual design.

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

### 1.1.1
- Fix slow reading of saedump files with large messages (e.g. with frames): `message_splitter()` now runs in linear instead of quadratic time and takes an optional `chunk_size` argument (default 1 MiB); output is unchanged

### 1.1.0
- Add optional consumer-lag backpressure (`enable_backpressure=True` on publisher and consumer); off by default and wire-compatible. Publisher exports lag via the `visionlib_stream_consumer_group_lag` Prometheus metric.

### 1.0.1
- Restrict pyturbojpeg to 1.x (2.x requires libjpeg-turbo 3.x, which is not available on Ubuntu 24.04 LTS)

### 1.0.0
- Migrate from redis-py to valkey-py
  - Use `valkey-py>=6.1.1`
  - Breaks compatibility: imports and constructor calls for consumer and publisher must be changed!
- Provide cleaner imports (`from visionlib.pipeline import ValkeyConsumer`)
