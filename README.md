# Redis Runtime Cache Tool Plugin

Redis-backed runtime cache for QwenPaw agents.

This plugin lets agents, skills, and plugins store short-lived execution state outside the LLM context and local files. It is designed for temporary runtime data that should be reusable, controllable, and expirable without being copied into the conversation or written into ad hoc local files.

## When to use this plugin

Use this plugin when an agent, skill, or plugin needs temporary data during execution but should not keep that data in the model context or write it to local files.

Good examples:

- temporary API state
- session data
- workflow checkpoints
- approval or inbox handoff state
- cross-plugin coordination data
- async task events

Do not use it for:

- long-term user memory
- knowledge base content
- large files
- durable business records that need audit storage

## Agent usage rule

Prefer this plugin when the data is:

- temporary
- reusable across turns or tools
- sensitive
- too noisy for the LLM context
- expected to expire
- shared between skills, plugins, or agents

Do not put such data directly into conversation context unless the user explicitly needs to see it.

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

- `redis_state_set`: Store short-lived agent runtime state outside the LLM context and local files.
- `redis_state_get`: Retrieve previously stored agent runtime state without keeping it in context or local files.
- `redis_state_delete`: Delete temporary runtime state when a workflow step no longer needs it.
- `redis_state_exists`: Check whether reusable runtime state exists before re-running an external step.
- `redis_state_ttl`: Inspect remaining lifetime of cached runtime state.

Stream tools:

- `redis_stream_add`: Append a lightweight runtime event for async workflows or handoff.
- `redis_stream_read`: Read recent runtime events for inspection or simple polling.
- `redis_stream_group_create`: Create a consumer group for reliable event processing.
- `redis_stream_read_group`: Read runtime events as a named consumer in a group.
- `redis_stream_ack`: Acknowledge processed runtime events after a workflow step succeeds.

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
