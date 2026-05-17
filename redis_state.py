# -*- coding: utf-8 -*-
"""Redis Runtime Cache Tool Plugin Entry Point."""

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
    """Redis-backed runtime cache for QwenPaw agents.

    The plugin helps agents, skills, and plugins store short-lived
    execution state outside the LLM context and local files.
    """

    def register(self, api: PluginApi):
        """Register Redis Runtime Cache tools.

        Args:
            api: PluginApi instance.
        """
        tool = _load_tool_module()

        api.register_tool(
            tool_name="redis_state_set",
            tool_func=tool.redis_state_set,
            description=(
                "Store short-lived agent runtime state outside the LLM "
                "context and local files"
            ),
            icon="🧠",
        )

        api.register_tool(
            tool_name="redis_state_get",
            tool_func=tool.redis_state_get,
            description=(
                "Retrieve stored agent runtime state without keeping it "
                "in conversation context or local files"
            ),
            icon="📦",
        )

        api.register_tool(
            tool_name="redis_state_delete",
            tool_func=tool.redis_state_delete,
            description=(
                "Delete temporary runtime state that a skill, plugin, "
                "or workflow no longer needs"
            ),
            icon="🗑️",
        )

        api.register_tool(
            tool_name="redis_state_exists",
            tool_func=tool.redis_state_exists,
            description=(
                "Check whether reusable runtime state exists before "
                "re-running an external tool or API step"
            ),
            icon="🔎",
        )

        api.register_tool(
            tool_name="redis_state_ttl",
            tool_func=tool.redis_state_ttl,
            description=(
                "Inspect remaining lifetime of cached runtime state to "
                "decide whether it should be reused or refreshed"
            ),
            icon="⏳",
        )

        api.register_tool(
            tool_name="redis_stream_add",
            tool_func=tool.redis_stream_add,
            description=(
                "Append a lightweight runtime event for async workflows "
                "or agent handoff"
            ),
            icon="📨",
        )

        api.register_tool(
            tool_name="redis_stream_read",
            tool_func=tool.redis_stream_read,
            description="Read recent runtime events for inspection or polling",
            icon="📬",
        )

        api.register_tool(
            tool_name="redis_stream_group_create",
            tool_func=tool.redis_stream_group_create,
            description=(
                "Create a consumer group for reliable runtime event "
                "processing by agents or workers"
            ),
            icon="👥",
        )

        api.register_tool(
            tool_name="redis_stream_read_group",
            tool_func=tool.redis_stream_read_group,
            description=(
                "Read runtime events as a named consumer in a reliable "
                "consumer group"
            ),
            icon="📥",
        )

        api.register_tool(
            tool_name="redis_stream_ack",
            tool_func=tool.redis_stream_ack,
            description=(
                "Acknowledge processed runtime events after a workflow "
                "step completes successfully"
            ),
            icon="✅",
        )

        logger.info("Redis Runtime Cache tool plugin registered")


# Export plugin instance
plugin = RedisStateToolPlugin()
