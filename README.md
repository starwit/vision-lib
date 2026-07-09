# vision-lib

Common components shared by the stages of the [Starwit Awareness Engine](https://github.com/starwit/starwit-awareness-engine) (SAE).

SAE stages communicate by passing `SaeMessage` protobufs (defined in [vision-api](https://github.com/starwit/vision-api)) through [Valkey](https://valkey.io/) streams. This library bundles the pieces most stages need:

- **Pipeline I/O** – read and write protobuf messages to/from Valkey streams.
- **Message helpers** – validate messages and extract raw/JPEG video frames.
- **Testing helpers** – record and replay traffic via the `.saedump` file format (see [format spec](./doc/saedump-format.md)).

Functionality is provided for both Python and Java. Since all SAE stages are written in Python, the [Python package](./python) is the primary one and offers the fuller feature set; the [Java package](./java) covers stream reading/writing and dump replay.

## Packages

| Package | Coordinates | Docs |
| --- | --- | --- |
| Python | `visionlib` | [python/README.md](./python/README.md) |
| Java | `de.starwit:vision-lib` | [java/README.md](./java/README.md) |
