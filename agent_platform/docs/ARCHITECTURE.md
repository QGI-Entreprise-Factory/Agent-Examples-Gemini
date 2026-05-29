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
        agp CLI (cli.py) ───────────────┐  drives every layer below
                                         ▼
┌─────────────────────────────────────────────────────────────┐
│  Web Console (frontend/index.html)                            │
│     browse · filter · streaming chat (fetch + ReadableStream) │
└───────────────┬───────────────────────────────────────────────┘
                │ HTTP/JSON + SSE
┌───────────────▼───────────────────────────────────────────────┐
│  API Gateway (backend/app.py — FastAPI)                        │
│   /api/agents · /{id} · /{id}/run · /{id}/stream (SSE)         │
│   sessions · graceful degradation when ADK/creds absent        │
└───────┬───────────────────────────────┬───────────────────────┘
        │ reads                          │ imports + runs (stream)
┌───────▼────────────┐         ┌─────────▼──────────────────────┐
│ Registry            │         │  ADK Runner (runner.py)         │
│  build_registry.py  │         │  dynamic import of root_agent   │
│  -> agents.json     │         │  InMemoryRunner + run_async     │
└─────────────────────┘         └─────────────────────────────────┘
        ▲ scans                           ▲ targets
┌───────┴─────────────────────────────────┴──────────────────────┐
│  Sample agents (python/ typescript/ go/ java/)                  │
│  + builtin_agents/echo (credential-free, for e2e)              │
│  Studio (studio/) scaffolds NEW agents · Deploy (deploy/)       │
└──────────────────────────────────────────────────────────────────┘
```

| # | Layer | Module | Status |
|---|-------|--------|--------|
| 1 | **Registry** — auto-discovery → `agents.json` | `registry/build_registry.py` | ✅ 80+ agents, 9 categories, offline |
| 2 | **API Gateway** — catalog + run + **SSE stream** | `backend/app.py`, `registry.py`, `runner.py` | ✅ catalog always; run/stream when ADK present |
| 3 | **Web Console** — browse + **streaming chat** | `frontend/index.html` | ✅ zero-build SPA, live token stream |
| 4 | **CLI** — `agp` drives the whole platform | `cli.py`, `__main__.py` | ✅ doctor/list/show/run/serve/new/test |
| 5 | **Studio** — scaffold new agents | `studio/create_agent.py` + templates | ✅ create → register → appears |
| 6 | **Builtin agent** — credential-free e2e | `builtin_agents/echo/` | ✅ real ADK BaseAgent, no creds |
| 7 | **Tests** — light + full e2e | `tests/` | ✅ registry/API unit + e2e via echo |
| 8 | **Deploy** — host gateway / per-agent | `deploy/` | ✅ Dockerfile + Cloud Run notes |

## Streaming

`/api/agents/{id}/stream` returns Server-Sent Events. The runner wraps ADK's
`run_async` async-generator and emits one SSE frame per event: a `session`
frame first, `message` frames carrying `partial` token chunks and the final
aggregated response, then `done`. The console consumes this with `fetch` +
`ReadableStream` and renders tokens as they arrive. This mirrors the ADK
"progressive SSE" pattern (partial chunks → single final aggregated response).

## End-to-end without credentials

`builtin/echo` is a real ADK `BaseAgent` run through the real `Runner`, but it
does not call an LLM — so the **full request → runner → SSE → response loop is
exercised in CI with no GCP credentials and no network**. `agp test --e2e`
validates the runner stream, the `/run` endpoint, the `/stream` SSE frames, and
session continuity against it.

## What this does NOT do yet

Next steps to harden into a production product:

- **Persistence** — sessions are in-memory (`_SESSIONS` + `InMemoryRunner`).
  Swap for `VertexAiSessionService` or a DB-backed session store.
- **AuthN/Z & multi-tenancy** — add an identity layer (IAP / OAuth) and
  per-user/project isolation; gate `/run` and `/stream` behind it.
- **Non-Python execution** — the runner executes Python + builtin agents. TS/Go/Java
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
