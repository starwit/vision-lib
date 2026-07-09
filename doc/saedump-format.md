# `.saedump` file format

An `.saedump` file records the `SaeMessage` traffic of one or more Valkey streams so it can be replayed later (e.g. for testing a stage without live input).

## Structure

A dump is a **UTF-8 text file** consisting of JSON objects separated by a semicolon (`;`), including a trailing separator after the last object:

```
<header>;<event>;<event>; … ;
```

- The **first** object is a *header* describing the dump.
- Every **following** object is an *event* wrapping a single recorded message.

The events are self-contained JSON objects separated by `;`, such that dump can trivially be read incrementally without loading the whole file into memory.

## Header

```json
{
  "start_time": 1720187724.6267505,
  "recorded_streams": ["geomapper:stream1"]
}
```

| Field | Type | Description |
| --- | --- | --- |
| `start_time` | float | Unix timestamp (seconds) when recording started. |
| `recorded_streams` | string[] | Keys of the streams contained in this dump. |

## Event

```json
{
  "meta": {
    "record_time": 1720187724.685442,
    "source_stream": "geomapper:stream1"
  },
  "data_b64": "ChoKB3N0cmVhbTEQ…"
}
```

| Field | Type | Description |
| --- | --- | --- |
| `meta.record_time` | float | Unix timestamp (seconds) when the message was recorded. |
| `meta.source_stream` | string | Stream the message was read from. |
| `data_b64` | string | Base64-encoded `SaeMessage` protobuf (as defined in [vision-api](https://github.com/starwit/vision-api)). |

The `data_b64` value can essentially be taken verbatim from a Valkey stream entry and it also can be written into a stream on playback.

## Reading a dump

- **Python:** `visionlib.saedump` – `message_splitter()` yields the raw objects; parse the first with `DumpMeta` and the rest with `Event`.
- **Java:** `de.starwit.testing.SaeDump` – iterate to receive decoded `SaeMessage` objects.
