# Copyright 2025 Google LLC
# Licensed under the Apache License, Version 2.0.
"""Full end-to-end tests: drive a real ADK agent through the platform.

These use the credential-free `builtin/echo` agent, so they exercise the
complete request -> Runner -> event/SSE -> response loop without any GCP or
network setup. Marked `e2e` so they can be selected/skipped explicitly.
"""

from __future__ import annotations

import json

import pytest

from agent_platform.backend import runner

pytestmark = pytest.mark.e2e


@pytest.mark.asyncio
async def test_runner_streams_echo():
    """The runner imports the real agent and streams partial + final events."""
    session = runner.AgentSession("builtin/echo")
    events = [ev async for ev in session.stream("hello world")]
    assert events, "expected at least one event"
    assert any(ev["partial"] for ev in events), "expected streamed partial chunks"
    finals = [ev for ev in events if ev["is_final"] and ev["text"]]
    assert finals and finals[-1]["text"] == "echo: hello world"


def test_run_endpoint_executes_echo(client):
    """POST /run returns the aggregated agent response."""
    r = client.post("/api/agents/builtin/echo/run", json={"message": "ping"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["session_id"]
    texts = [e["text"] for e in body["events"] if e["is_final"] and e["text"]]
    assert texts and texts[-1] == "echo: ping"


def test_stream_endpoint_emits_sse(client):
    """POST /stream emits SSE frames: session, message(s), done."""
    with client.stream(
        "POST", "/api/agents/builtin/echo/stream", json={"message": "stream me"}
    ) as resp:
        assert resp.status_code == 200
        raw = "".join(chunk for chunk in resp.iter_text())

    assert "event: session" in raw
    assert "event: message" in raw
    assert "event: done" in raw
    # The final aggregated message must be present in the stream.
    assert "echo: stream me" in raw


def test_session_continuity(client):
    """Reusing a session_id keeps the same conversation/runner."""
    first = client.post(
        "/api/agents/builtin/echo/run", json={"message": "one"}
    ).json()
    sid = first["session_id"]
    second = client.post(
        "/api/agents/builtin/echo/run", json={"message": "two", "session_id": sid}
    ).json()
    assert second["session_id"] == sid
