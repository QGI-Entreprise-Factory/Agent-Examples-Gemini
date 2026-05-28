# ADK Agent Platform — Architecture & Roadmap

## Problem

This repo is a **catalog of 80+ standalone ADK sample agents** across Python,
TypeScript, Go, and Java. Each is excellent in isolation but there is no
unified way to **discover, run, build, or deploy** them. "Turning it into an
agent AI platform" means adding a thin product layer on top of the samples —
without forking or rewriting them.

## Key leverage point

Every Python sample follows the same ADK convention:

```
python/agents/<agent>/<package>/agent.py   ->  exports `root_agent`
python/agents/<agent>/pyproject.toml        ->  name + description
python/agents/<agent>/README.md             ->  docs
python/agents/<agent>/deployment/deploy.py  ->  Vertex Agent Engine deploy
```

The platform keys off `root_agent` and the directory layout, so **new samples
are picked up automatically** with zero per-agent wiring.

## The five layers

```
┌─────────────────────────────────────────────────────────────┐
│  3. Web Console (frontend/index.html)                         │
│     browse catalog · filter · open agent · chat               │
└───────────────┬───────────────────────────────────────────────┘
                │ HTTP/JSON
┌───────────────▼───────────────────────────────────────────────┐
│  2. API Gateway (backend/app.py — FastAPI)                     │
│     /api/agents  ·  /api/agents/{id}  ·  /api/agents/{id}/run  │
│     sessions · graceful degradation when ADK/creds absent       │
└───────┬───────────────────────────────┬───────────────────────┘
        │ reads                          │ imports + runs
┌───────▼────────────┐         ┌─────────▼──────────────────────┐
│ 1. Registry         │         │  ADK Runner (runner.py)         │
│  build_registry.py  │         │  dynamic import of root_agent   │
│  -> agents.json     │         │  InMemoryRunner + sessions      │
└─────────────────────┘         └─────────────────────────────────┘
        ▲                                 ▲
        │ scans                           │ targets
┌───────┴─────────────────────────────────┴──────────────────────┐
│  Existing sample agents  (python/ typescript/ go/ java/)        │
│  4. Studio (studio/create_agent.py) scaffolds NEW ones here     │
│  5. Deploy (deploy/) containerizes gateway; per-agent → Vertex  │
└──────────────────────────────────────────────────────────────────┘
```

| # | Layer | Module | Status (prototype) |
|---|-------|--------|--------------------|
| 1 | **Registry** — auto-discovery → `agents.json` | `registry/build_registry.py` | ✅ 80 agents, 9 categories, offline |
| 2 | **API Gateway** — unified catalog + run API | `backend/app.py`, `registry.py`, `runner.py` | ✅ catalog always; run when ADK present |
| 3 | **Web Console** — browse + chat | `frontend/index.html` | ✅ zero-build SPA |
| 4 | **Studio** — scaffold new agents | `studio/create_agent.py` + templates | ✅ create → register → appears |
| 5 | **Deploy** — host gateway / per-agent | `deploy/Dockerfile`, `deploy/README.md` | ✅ Dockerfile + Cloud Run notes |

## What the prototype intentionally does NOT do yet

These are the next steps to harden it into a real product:

- **Persistence** — sessions are in-memory. Swap `InMemoryRunner` /
  `_SESSIONS` for `VertexAiSessionService` or a DB-backed session store.
- **Streaming** — `/run` returns the full turn. Add SSE/WebSocket to stream
  tokens and tool-call events to the console.
- **AuthN/Z & multi-tenancy** — add an identity layer (IAP / OAuth) and
  per-user/project isolation; gate `/run` behind it.
- **Non-Python execution** — the runner executes Python agents. TS/Go/Java
  agents are catalogued but run via their own ADK servers; the gateway could
  proxy to them over **A2A** (agent-to-agent protocol).
- **Observability** — wire the existing `agent-observability-bq` pattern in as
  a cross-cutting middleware (traces, token usage, cost per agent).
- **Agent-to-agent routing** — a meta-router agent that picks the right
  sample agent for a request (turning the catalog into one front-door agent).
- **CI** — a job that runs `build_registry.py` and fails if the manifest is
  stale, keeping the catalog honest.

## Design choices

- **Generated manifest, not live import for the catalog.** Discovery is a
  static scan so the catalog loads instantly and works with no dependencies,
  credentials, or network. Heavy imports happen lazily, only when an agent is
  actually run.
- **Graceful degradation.** Missing `google-adk` or GCP creds never breaks
  browsing — only `/run` returns an actionable `503`.
- **Non-invasive.** No sample agent is modified. The platform is additive and
  lives entirely under `agent_platform/`.
- **Named `agent_platform/`, not `platform/`** to avoid shadowing Python's
  stdlib `platform` module.
