# -*- coding: utf-8 -*-
"""Redis temporary runtime state and stream tools.

This module exposes Redis-backed utilities for QwenPaw agents that need
short-lived runtime state, OAuth/session caches, workflow checkpoints,
or lightweight event streams.
"""

import json
import logging
import re
from typing import Any

import redis
from agentscope.message import TextBlock
from agentscope.tool import ToolResponse
from qwenpaw.plugins import get_tool_config

logger = logging.getLogger(__name__)

CONFIG_TOOL_NAME = "redis_state_set"
KEY_PATTERN = re.compile(r"^[a-zA-Z0-9:_\-.]+$")
SENSITIVE_FIELDS = {
    "access_token",
    "refresh_token",
    "api_key",
    "authorization",
    "cookie",
    "session",
    "password",
}


class RedisStateError(Exception):
    """Raised when Redis State tool input is invalid."""


class RedisConfigError(Exception):
    """Raised when shared Redis configuration is missing or invalid."""


def _response(text: str) -> ToolResponse:
    return ToolResponse(
        content=[TextBlock(type="text", text=text)],
    )


def _json_response(payload: Any) -> ToolResponse:
    return _response(json.dumps(payload, ensure_ascii=False, indent=2))


def _to_int(value: Any, default: int, field_name: str) -> int:
    if value is None or value == "":
        return default

    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise RedisStateError(
            f"{field_name} must be an integer, got {value!r}",
        ) from exc

    if parsed <= 0:
        raise RedisStateError(f"{field_name} must be greater than 0")

    return parsed


def _get_config() -> dict:
    """Read shared Redis configuration from redis_state_set.

    QwenPaw stores configuration on individual tools. To avoid asking the
    user to configure the same Redis connection repeatedly, this plugin
    uses redis_state_set as the canonical configuration holder. All Redis
    tools read the same config from that tool.
    """
    config = get_tool_config(CONFIG_TOOL_NAME)

    if not config:
        raise RedisConfigError(
            "Redis is not configured. Configure redis_state_set once in "
            "Tool Settings; all Redis tools share that configuration.",
        )

    return config


def _get_redis():
    config = _get_config()
    redis_url = config.get("redis_url")

    if not redis_url:
        raise RedisConfigError("redis_url is required")

    return redis.from_url(redis_url, decode_responses=True), config


def _mask_sensitive(value: Any):
    if isinstance(value, dict):
        masked = {}
        for key, item in value.items():
            if key.lower() in SENSITIVE_FIELDS:
                masked[key] = "***MASKED***"
            else:
                masked[key] = _mask_sensitive(item)
        return masked

    if isinstance(value, list):
        return [_mask_sensitive(item) for item in value]

    return value


def _namespace_key(key: str, namespace: str) -> str:
    if not key:
        raise RedisStateError("key is required")

    if not KEY_PATTERN.match(key):
        raise RedisStateError(
            "invalid key format; allowed chars: a-z A-Z 0-9 : _ - .",
        )

    return f"{namespace}:{key}"


def _build_key(config: dict, key: str, namespace: str) -> str:
    key_prefix = config.get("key_prefix", "qwenpaw")
    return _namespace_key(key, f"{key_prefix}:{namespace}")


def _decode_json_field(value: str) -> Any:
    try:
        return json.loads(value)
    except Exception:
        return value


async def redis_state_set(
    key: str,
    value: Any,
    ttl_seconds: int | str | None = None,
    namespace: str = "runtime",
) -> ToolResponse:
    """Store temporary runtime state in Redis with TTL.

    Use this tool when an agent needs to keep short-lived data such as
    OAuth tokens, API session IDs, checkpoint payloads, or tool execution
    state across turns or across cooperating agents.

    Args:
        key: Logical key under the configured namespace. Allowed chars are
            letters, numbers, colon, underscore, dash, and dot.
        value: JSON-serializable value to store.
        ttl_seconds: Optional TTL override. String numbers are accepted and
            normalized. The value is capped by max_ttl_seconds.
        namespace: Logical namespace under the configured key_prefix.
            Defaults to "runtime".

    Returns:
        ToolResponse containing the final Redis key and TTL.
    """
    try:
        redis_client, config = _get_redis()

        default_ttl = _to_int(
            config.get("default_ttl_seconds"),
            3600,
            "default_ttl_seconds",
        )
        max_ttl = _to_int(
            config.get("max_ttl_seconds"),
            86400,
            "max_ttl_seconds",
        )
        max_value_bytes = _to_int(
            config.get("max_value_bytes"),
            65536,
            "max_value_bytes",
        )

        redis_key = _build_key(config, key, namespace)
        ttl = min(_to_int(ttl_seconds, default_ttl, "ttl_seconds"), max_ttl)
        payload = json.dumps(value, ensure_ascii=False)

        if len(payload.encode("utf-8")) > max_value_bytes:
            raise RedisStateError("value exceeds max_value_bytes")

        redis_client.set(redis_key, payload, ex=ttl)

        return _json_response(
            {
                "success": True,
                "key": redis_key,
                "ttl_seconds": ttl,
            },
        )

    except Exception as exc:
        logger.error("redis_state_set failed: %s", exc, exc_info=True)
        return _response(f"Error storing Redis state: {str(exc)}")


async def redis_state_get(
    key: str,
    namespace: str = "runtime",
    reveal_sensitive: bool = False,
) -> ToolResponse:
    """Read temporary runtime state from Redis.

    Sensitive fields are masked by default to avoid leaking access tokens,
    refresh tokens, API keys, cookies, sessions, or passwords into user
    visible output.

    Args:
        key: Logical key to read.
        namespace: Logical namespace under the configured key_prefix.
            Defaults to "runtime".
        reveal_sensitive: Set to true only when the caller explicitly needs
            the raw value for another internal tool step.

    Returns:
        ToolResponse containing the decoded JSON value, or a not-found
        response when the key does not exist.
    """
    try:
        redis_client, config = _get_redis()
        redis_key = _build_key(config, key, namespace)
        raw = redis_client.get(redis_key)

        if raw is None:
            return _json_response(
                {"exists": False, "key": redis_key},
            )

        value = _decode_json_field(raw)
        if not reveal_sensitive:
            value = _mask_sensitive(value)

        return _json_response(
            {"exists": True, "key": redis_key, "value": value},
        )

    except Exception as exc:
        logger.error("redis_state_get failed: %s", exc, exc_info=True)
        return _response(f"Error reading Redis state: {str(exc)}")


async def redis_state_delete(
    key: str,
    namespace: str = "runtime",
) -> ToolResponse:
    """Delete temporary runtime state from Redis.

    Args:
        key: Logical key to delete.
        namespace: Logical namespace under the configured key_prefix.
            Defaults to "runtime".

    Returns:
        ToolResponse indicating whether a key was deleted.
    """
    try:
        redis_client, config = _get_redis()
        redis_key = _build_key(config, key, namespace)
        deleted = redis_client.delete(redis_key)

        return _json_response(
            {"key": redis_key, "deleted": bool(deleted)},
        )

    except Exception as exc:
        logger.error("redis_state_delete failed: %s", exc, exc_info=True)
        return _response(f"Error deleting Redis state: {str(exc)}")


async def redis_state_exists(
    key: str,
    namespace: str = "runtime",
) -> ToolResponse:
    """Check whether temporary runtime state exists in Redis.

    Args:
        key: Logical key to check.
        namespace: Logical namespace under the configured key_prefix.
            Defaults to "runtime".

    Returns:
        ToolResponse containing an exists boolean.
    """
    try:
        redis_client, config = _get_redis()
        redis_key = _build_key(config, key, namespace)
        exists = bool(redis_client.exists(redis_key))

        return _json_response(
            {"key": redis_key, "exists": exists},
        )

    except Exception as exc:
        logger.error("redis_state_exists failed: %s", exc, exc_info=True)
        return _response(f"Error checking Redis state: {str(exc)}")


async def redis_state_ttl(
    key: str,
    namespace: str = "runtime",
) -> ToolResponse:
    """Get remaining TTL for a temporary Redis state key.

    Redis returns -2 when the key does not exist and -1 when the key exists
    but has no expiration.

    Args:
        key: Logical key to inspect.
        namespace: Logical namespace under the configured key_prefix.
            Defaults to "runtime".

    Returns:
        ToolResponse containing the Redis key and ttl_seconds.
    """
    try:
        redis_client, config = _get_redis()
        redis_key = _build_key(config, key, namespace)
        ttl = redis_client.ttl(redis_key)

        return _json_response(
            {"key": redis_key, "ttl_seconds": ttl},
        )

    except Exception as exc:
        logger.error("redis_state_ttl failed: %s", exc, exc_info=True)
        return _response(f"Error reading Redis TTL: {str(exc)}")


async def redis_stream_add(
    stream: str,
    event: dict,
    namespace: str = "stream",
) -> ToolResponse:
    """Append an event object to a Redis Stream.

    Use this for lightweight async workflow events, handoff queues,
    approval events, or subagent coordination signals. The event is stored
    under a single JSON field named "data".

    Args:
        stream: Logical stream name.
        event: JSON-serializable event object.
        namespace: Logical namespace under the configured key_prefix.
            Defaults to "stream".

    Returns:
        ToolResponse containing the stream key and generated message ID.
    """
    try:
        redis_client, config = _get_redis()
        stream_key = _build_key(config, stream, namespace)
        event_id = redis_client.xadd(
            stream_key,
            {"data": json.dumps(event, ensure_ascii=False)},
        )

        return _json_response(
            {"stream": stream_key, "id": event_id},
        )

    except Exception as exc:
        logger.error("redis_stream_add failed: %s", exc, exc_info=True)
        return _response(f"Error adding Redis stream event: {str(exc)}")


async def redis_stream_read(
    stream: str,
    count: int | str = 10,
    namespace: str = "stream",
) -> ToolResponse:
    """Read recent events from a Redis Stream without consumer groups.

    This is useful for quick inspection or simple polling. For reliable
    multi-consumer processing, use redis_stream_group_create,
    redis_stream_read_group, and redis_stream_ack instead.

    Args:
        stream: Logical stream name.
        count: Maximum number of recent messages to return. String numbers
            are accepted and normalized.
        namespace: Logical namespace under the configured key_prefix.
            Defaults to "stream".

    Returns:
        ToolResponse containing recent stream entries in reverse order.
    """
    try:
        redis_client, config = _get_redis()
        count_value = _to_int(count, 10, "count")
        stream_key = _build_key(config, stream, namespace)
        entries = redis_client.xrevrange(stream_key, count=count_value)

        parsed = []
        for entry_id, data in entries:
            parsed.append(
                {
                    "id": entry_id,
                    "data": _decode_json_field(data.get("data", "{}")),
                },
            )

        return _json_response(parsed)

    except Exception as exc:
        logger.error("redis_stream_read failed: %s", exc, exc_info=True)
        return _response(f"Error reading Redis stream: {str(exc)}")


async def redis_stream_group_create(
    stream: str,
    group: str,
    start_id: str = "0",
    namespace: str = "stream",
) -> ToolResponse:
    """Create a Redis Stream consumer group.

    Args:
        stream: Logical stream name.
        group: Consumer group name.
        start_id: Stream ID to start from. Use "0" to process from the
            beginning, or "$" to process only new messages.
        namespace: Logical namespace under the configured key_prefix.
            Defaults to "stream".

    Returns:
        ToolResponse indicating whether the group was created or already
        existed.
    """
    try:
        redis_client, config = _get_redis()
        stream_key = _build_key(config, stream, namespace)

        try:
            redis_client.xgroup_create(
                stream_key,
                group,
                id=start_id,
                mkstream=True,
            )
            created = True
        except redis.ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise
            created = False

        return _json_response(
            {"stream": stream_key, "group": group, "created": created},
        )

    except Exception as exc:
        logger.error(
            "redis_stream_group_create failed: %s",
            exc,
            exc_info=True,
        )
        return _response(f"Error creating Redis stream group: {str(exc)}")


async def redis_stream_read_group(
    stream: str,
    group: str,
    consumer: str,
    count: int | str = 10,
    block_ms: int | str = 0,
    namespace: str = "stream",
) -> ToolResponse:
    """Read Redis Stream events as a consumer-group consumer.

    Args:
        stream: Logical stream name.
        group: Consumer group name.
        consumer: Consumer name, usually an agent or worker identifier.
        count: Maximum number of new messages to return.
        block_ms: Blocking timeout in milliseconds. Use 0 for no blocking.
        namespace: Logical namespace under the configured key_prefix.
            Defaults to "stream".

    Returns:
        ToolResponse containing messages assigned to the consumer. Messages
        should be acknowledged with redis_stream_ack after successful
        processing.
    """
    try:
        redis_client, config = _get_redis()
        stream_key = _build_key(config, stream, namespace)
        count_value = _to_int(count, 10, "count")
        block_value = _to_int(block_ms, 1, "block_ms") if block_ms else 0

        entries = redis_client.xreadgroup(
            groupname=group,
            consumername=consumer,
            streams={stream_key: ">"},
            count=count_value,
            block=block_value,
        )

        parsed = []
        for resolved_stream, messages in entries:
            for message_id, data in messages:
                parsed.append(
                    {
                        "stream": resolved_stream,
                        "id": message_id,
                        "data": _decode_json_field(data.get("data", "{}")),
                    },
                )

        return _json_response(parsed)

    except Exception as exc:
        logger.error("redis_stream_read_group failed: %s", exc, exc_info=True)
        return _response(f"Error reading Redis stream group: {str(exc)}")


async def redis_stream_ack(
    stream: str,
    group: str,
    message_ids: list[str] | str,
    namespace: str = "stream",
) -> ToolResponse:
    """Acknowledge Redis Stream messages in a consumer group.

    Args:
        stream: Logical stream name.
        group: Consumer group name.
        message_ids: One message ID string or a list of message IDs to ack.
        namespace: Logical namespace under the configured key_prefix.
            Defaults to "stream".

    Returns:
        ToolResponse containing the number of acknowledged messages.
    """
    try:
        redis_client, config = _get_redis()
        stream_key = _build_key(config, stream, namespace)
        ids = [message_ids] if isinstance(message_ids, str) else message_ids
        acked = redis_client.xack(stream_key, group, *ids)

        return _json_response(
            {"stream": stream_key, "group": group, "acked": acked},
        )

    except Exception as exc:
        logger.error("redis_stream_ack failed: %s", exc, exc_info=True)
        return _response(f"Error acknowledging Redis stream message: {str(exc)}")
