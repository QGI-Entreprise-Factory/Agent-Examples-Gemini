# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Unified API gateway for the ADK agent platform.

Endpoints:
  GET  /api/health
  GET  /api/agents                      list + filter (language, category, q)
  GET  /api/agents/{lang}/{name}        agent detail (+ README)
  POST /api/agents/{lang}/{name}/run    run one turn (requires google-adk + creds)
  POST /api/agents/{lang}/{name}/stream run one turn, streamed over SSE
  POST /api/agents/{lang}/{name}/stream run one turn, streamed over SSE

The catalog endpoints are always available. Execution degrades gracefully when
the ADK or credentials are absent.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from . import registry, runner

FRONTEND_DIR = registry.REPO_ROOT / "agent_platform" / "frontend"

app = FastAPI(title="ADK Agent Platform", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory session store: {session_id: AgentSession}. Swap for Redis/DB in prod.
_SESSIONS: dict[str, runner.AgentSession] = {}


class RunRequest(BaseModel):
    message: str
    session_id: str | None = None


class RunResponse(BaseModel):
    session_id: str
    events: list[dict]


@app.get("/api/health")
def health() -> dict:
    manifest = registry.load_manifest()
    return {
        "status": "ok",
        "agent_count": manifest["agent_count"],
        "adk_available": runner.adk_available(),
    }


@app.get("/api/agents")
def list_agents(
    language: str | None = Query(default=None),
    category: str | None = Query(default=None),
    q: str | None = Query(default=None),
) -> dict:
    manifest = registry.load_manifest()
    agents = registry.list_agents(language=language, category=category, query=q)
    return {
        "count": len(agents),
        "languages": manifest["languages"],
        "categories": manifest["categories"],
        "agents": agents,
    }


@app.get("/api/agents/{language}/{name}")
def get_agent(language: str, name: str) -> dict:
    agent_id = f"{language}/{name}"
    agent = registry.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")
    return {**agent, "readme": registry.get_readme(agent_id)}


@app.post("/api/agents/{language}/{name}/run", response_model=RunResponse)
async def run_agent(language: str, name: str, req: RunRequest) -> RunResponse:
    agent_id = f"{language}/{name}"
    if not registry.get_agent(agent_id):
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")

    session_id = req.session_id or str(uuid.uuid4())
    session = _SESSIONS.get(session_id)
    try:
        if session is None or session.agent_id != agent_id:
            session = runner.AgentSession(agent_id)
            _SESSIONS[session_id] = session
        events = await session.send(req.message)
    except runner.AgentExecutionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Agent error: {exc}") from exc
    return RunResponse(session_id=session_id, events=events)


@app.post("/api/agents/{language}/{name}/stream")
async def stream_agent(language: str, name: str, req: RunRequest):
    """Stream an agent turn over SSE (one event per ADK event)."""
    agent_id = f"{language}/{name}"
    if not registry.get_agent(agent_id):
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")

    session_id = req.session_id or str(uuid.uuid4())
    session = _SESSIONS.get(session_id)
    try:
        if session is None or session.agent_id != agent_id:
            session = runner.AgentSession(agent_id)
            _SESSIONS[session_id] = session
    except runner.AgentExecutionError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    async def event_source():
        yield {"event": "session", "data": json.dumps({"session_id": session_id})}
        try:
            async for ev in session.stream(req.message):
                yield {"event": "message", "data": json.dumps(ev)}
        except Exception as exc:  # noqa: BLE001
            yield {"event": "error", "data": json.dumps({"detail": str(exc)})}
        yield {"event": "done", "data": "{}"}

    return EventSourceResponse(event_source())


# --- Static web console (mounted last so /api/* wins) ---------------------
if FRONTEND_DIR.is_dir():

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(FRONTEND_DIR / "index.html")

    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR)), name="frontend")
