# Copyright 2025 Google LLC
# Licensed under the Apache License, Version 2.0.
"""Light API tests against the FastAPI gateway (catalog path)."""

from __future__ import annotations


def test_health(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["agent_count"] > 50


def test_list_and_filter(client):
    all_agents = client.get("/api/agents").json()
    assert all_agents["count"] > 50
    finance = client.get("/api/agents?category=finance").json()
    assert all(a["category"] == "finance" for a in finance["agents"])


def test_detail_includes_readme(client):
    d = client.get("/api/agents/builtin/echo").json()
    assert d["id"] == "builtin/echo"
    assert d["readme"]


def test_unknown_agent_404(client):
    assert client.get("/api/agents/python/does-not-exist").status_code == 404


def test_console_served(client):
    assert client.get("/").status_code == 200
