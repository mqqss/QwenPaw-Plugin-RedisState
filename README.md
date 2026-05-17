# Redis State Tool Plugin

Redis-backed shared runtime state and stream tools for QwenPaw agents.

This plugin is intended for short-lived runtime data, not long-term user memory. Typical use cases include temporary workflow state, API session cache, approval handoff state, lightweight async event streams, and subagent coordination signals.

## Configuration

QwenPaw currently stores configuration on individual tools. To avoid configuring the same Redis connection repeatedly, this plugin uses `redis_state_set` as the canonical configuration holder.

Configure Redis once on `redis_state_set`; all other Redis tools read the same configuration.

Required field:

- `redis_url`

Optional fields:

- `key_prefix`, default `qwenpaw`
- `default_ttl_seconds`, default `3600`
- `max_ttl_seconds`, default `86400`
- `max_value_bytes`, default `65536`

## Tools

State tools:

- `redis_state_set`: Store JSON-serializable temporary state with TTL.
- `redis_state_get`: Read state by key; masks sensitive fields by default.
- `redis_state_delete`: Delete state by key.
- `redis_state_exists`: Check whether state exists.
- `redis_state_ttl`: Read remaining TTL.

Stream tools:

- `redis_stream_add`: Append an event object to a Redis Stream.
- `redis_stream_read`: Read recent stream events without consumer groups.
- `redis_stream_group_create`: Create a stream consumer group.
- `redis_stream_read_group`: Read events as a consumer-group consumer.
- `redis_stream_ack`: Acknowledge one or more message IDs.

## Key format

Keys are generated as:

```text
{key_prefix}:{namespace}:{key}
```

Default namespace for state tools is `runtime`.
Default namespace for stream tools is `stream`.

## Safety notes

`redis_state_get` masks common sensitive field names by default. Pass `reveal_sensitive=true` only when a trusted internal tool step needs the raw value.

All numeric inputs are normalized internally because agent/tool arguments may arrive as strings.
