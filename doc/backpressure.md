# How backpressure works

This explains the mechanism behind the optional backpressure feature of `ValkeyConsumer` /
`ValkeyPublisher` (see the [Python README](../python/README.md) for how to turn it on). It is a
conceptual overview, not an API reference.

## The problem

Normally the publisher is fire-and-forget: it appends messages to a Valkey stream and trims that
stream to a maximum length so memory stays bounded. If a consumer is too slow, the oldest messages
are trimmed away before it reads them — they are simply lost. That is fine for live video, but wrong
for batch/replay, where every message must be processed. Backpressure makes the publisher *slow
down* to the consumer's pace instead of dropping messages, while still keeping the stream (and thus
memory) bounded.

## The core idea

The publisher and the consumer already run their work in a loop — the publisher keeps publishing,
the consumer keeps reading. So if we can make the *publish* call block while the consumer is behind,
the entire producer naturally slows down. The only thing we need is a reliable, cheap measure of
"how far behind is the consumer", and a way to pause the publisher on it.

That measure comes for free from **Valkey consumer groups**.

## Consumer groups as a lag signal

A consumer group is a server-side bookmark on a stream. Valkey tracks, per group, how many entries
have been added to the stream versus how many the group has read; the difference is the group's
**lag** — a pure count of undelivered messages, independent of timestamps or message contents.

- The publisher *owns* the stream, so it creates a default consumer group on every stream it writes
  to (a hardcoded group name, created the first time a stream is published to).
- A backpressure-aware consumer *attaches* to that same group and reads through it. Attaching is the
  whole point: it makes the consumer's progress visible to the publisher as the group's lag.

The consumer reads in **NOACK** mode — it takes messages from the group but does not acknowledge
them. This keeps the model simple: there is no pending-entries list to manage, and the lag is exactly
the number of messages not yet delivered to the group.

## Slowing the publisher down

Backpressure is applied by a gate that the publisher waits on before each write:

- While the lag is below a configured **threshold**, the gate is open and publishing proceeds at full
  speed.
- When the lag reaches the threshold, the gate closes and the next publish call blocks — stalling the
  producer's loop — until the consumer catches up enough to reopen it.

The threshold defaults to **half of the stream's trim length**. That is the key to being lossless and
memory-bounded at the same time: because the publisher stops letting the lag grow past half the
retained window, the undelivered messages always sit comfortably inside the part of the stream that
is still retained. Trimming therefore only ever discards messages the consumer has *already* read —
never an undelivered one. Memory stays bounded by the trim length; no message is dropped.

## The out-of-band monitor

The lag is not checked inline on the publish path. Instead a **background monitor thread** runs
alongside the publisher and, on a short interval:

- samples the group's lag and opens/closes the gate accordingly,
- exports the lag as a Prometheus metric,
- cleans up crashed consumers (see below),
- decides whether to fail open (see below).

A separate thread is essential rather than incidental: once the publisher is blocked on the gate it
cannot do anything itself, so the work that might *reopen* the gate — measuring lag, removing dead
consumers, failing open — has to happen independently of the blocked producer.

## Dead consumers and failing open

Two things can go wrong when consumers misbehave:

- **A consumer crashes.** It stops reading, so the group's position stops advancing and lag climbs.
  The monitor detects consumers that have been idle beyond a timeout and removes them from the group
  so they no longer count as participants.
- **Every consumer is gone.** If no live consumer remains, lag can never fall and the publisher would
  block forever. To avoid a permanent stall, the monitor **fails open** after a configurable timeout:
  it reopens the gate and lets the publisher resume (which means messages may again be trimmed/lost,
  logged as a warning). This is a deliberate trade-off — a stalled producer is usually worse than
  dropping messages during a total consumer outage. Recovery is automatic: as soon as a live consumer
  reappears, normal lag-based throttling resumes.

## Backwards and wire compatibility

The consumer group is just metadata attached to the stream; the messages on the wire are unchanged.
A plain (non-group) reader still reads the stream exactly as before and is unaffected by the group's
existence. Backpressure is opt-in on both ends, so mixed old/new publishers and consumers keep
working — just without the new throttling.

## A note on lag reliability

Valkey can only report the group's lag as an exact number while the group's read position is still
within the retained part of the stream. If undelivered messages were ever trimmed away (which only
happens *after* the lossless guarantee has already been violated — e.g. during a fail-open outage),
the exact lag becomes unavailable. In that degraded case the monitor falls back to counting the
messages still retained ahead of the group, so the publisher keeps making progress. In normal
operation the half-window threshold keeps the group well inside the retained range, so the exact lag
is always available.
