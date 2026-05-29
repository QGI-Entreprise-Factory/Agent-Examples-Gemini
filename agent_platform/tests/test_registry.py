# Copyright 2025 Google LLC
# Licensed under the Apache License, Version 2.0.
"""Light unit tests for the registry layer (no ADK / creds needed)."""

from __future__ import annotations

from agent_platform.backend import registry


def test_manifest_has_agents():
    m = registry.load_manifest()
    assert m["agent_count"] > 50
    assert "python" in m["languages"]


def test_every_entry_has_required_fields():
    required = {"id", "slug", "name", "language", "category", "path", "runnable"}
    for a in registry.load_manifest()["agents"]:
        assert required <= set(a), f"missing fields in {a.get('id')}"


def test_builtin_echo_is_registered_and_runnable():
    echo = registry.get_agent("builtin/echo")
    assert echo is not None, "builtin echo agent must be discoverable"
    assert echo["runnable"] is True
    assert echo["builtin"] is True


def test_filtering():
    py = registry.list_agents(language="python")
    assert all(a["language"] == "python" for a in py)
    hits = registry.list_agents(query="research")
    assert hits, "expected at least one research agent"
