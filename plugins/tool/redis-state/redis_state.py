# -*- coding: utf-8 -*-
"""Redis State Tool Plugin Entry Point."""

import importlib.util
import logging
import os

from qwenpaw.plugins.api import PluginApi

logger = logging.getLogger(__name__)

_PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))


def _load_tool_module():
    """Load redis_state_tool.py from this plugin's directory."""
    tool_path = os.path.join(_PLUGIN_DIR, "redis_state_tool.py")
    spec = importlib.util.spec_from_file_location(
        "redis_state_tool",
        tool_path,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RedisStateToolPlugin:
    """Redis-backed shared runtime state and stream tool plugin."""

    def register(self, api: PluginApi):
        """Register Redis State tools.

        Args:
            api: PluginApi instance.
        """
        tool = _load_tool_module()

        api.register_tool(
            tool_name="redis_state_set",
            tool_func=tool.redis_state_set,
            description=(
                "Store JSON-serializable temporary runtime state "
                "in Redis with TTL"
            ),
            icon="🧠",
        )

        api.register_tool(
            tool_name="redis_state_get",
            tool_func=tool.redis_state_get,
            description=(
                "Read temporary runtime state from Redis; "
                "sensitive fields are masked by default"
            ),
            icon="📦",
        )

        api.register_tool(
            tool_name="redis_state_delete",
            tool_func=tool.redis_state_delete,
            description="Delete temporary runtime state from Redis by key",
            icon="🗑️",
        )

        api.register_tool(
            tool_name="redis_state_exists",
            tool_func=tool.redis_state_exists,
            description="Check whether a temporary Redis state key exists",
            icon="🔎",
        )

        api.register_tool(
            tool_name="redis_state_ttl",
            tool_func=tool.redis_state_ttl,
            description="Get remaining TTL for a temporary Redis state key",
            icon="⏳",
        )

        api.register_tool(
            tool_name="redis_stream_add",
            tool_func=tool.redis_stream_add,
            description="Append an event object to a Redis Stream",
            icon="📨",
        )

        api.register_tool(
            tool_name="redis_stream_read",
            tool_func=tool.redis_stream_read,
            description="Read recent events from a Redis Stream",
            icon="📬",
        )

        api.register_tool(
            tool_name="redis_stream_group_create",
            tool_func=tool.redis_stream_group_create,
            description="Create a Redis Stream consumer group",
            icon="👥",
        )

        api.register_tool(
            tool_name="redis_stream_read_group",
            tool_func=tool.redis_stream_read_group,
            description="Read Redis Stream events as a consumer group consumer",
            icon="📥",
        )

        api.register_tool(
            tool_name="redis_stream_ack",
            tool_func=tool.redis_stream_ack,
            description="Acknowledge Redis Stream messages in a consumer group",
            icon="✅",
        )

        logger.info("Redis State tool plugin registered")


# Export plugin instance
plugin = RedisStateToolPlugin()
