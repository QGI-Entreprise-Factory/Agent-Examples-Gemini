# ADK Agent Platform

Turns this repo's collection of **80+ standalone ADK sample agents** into a
single, runnable **agent AI platform**: discover every agent, browse them in a
web console, chat with any runnable one through a unified API, scaffold new
agents, and deploy.

It is **additive and non-invasive** — no sample agent is modified. The platform
keys off the existing ADK `root_agent` convention, so new samples appear
automatically.

> See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the design and roadmap.

## Layers

| Layer | Path | What it does |
|-------|------|--------------|
| Registry | `registry/build_registry.py` | Scans the repo → `agents.json` (offline) |
| API Gateway | `backend/app.py` | FastAPI: list / detail / run agents |
| Web Console | `frontend/index.html` | Browse, filter, and chat with agents |
| Studio | `studio/create_agent.py` | Scaffold a new agent from a template |
| Deploy | `deploy/` | Containerize the gateway; per-agent → Vertex |

## Quickstart

```bash
# 1. Build the catalog (no deps, no creds needed)
python agent_platform/registry/build_registry.py

# 2. Install the gateway and run it
pip install -r agent_platform/backend/requirements.txt
uvicorn agent_platform.backend.app:app --reload

# 3. Open the console
open http://localhost:8000
```

The **catalog, search, and agent detail views work immediately** with no
credentials. To actually *run* an agent (the `/run` endpoint), you need
`google-adk` installed (in `requirements.txt`) plus the GCP/Vertex credentials
that the specific sample agent expects — see that agent's `.env.example`.

## API

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/api/health` | Status + agent count + whether execution is available |
| `GET` | `/api/agents?language=&category=&q=` | List / filter the catalog |
| `GET` | `/api/agents/{language}/{name}` | Agent detail + README |
| `POST`| `/api/agents/{language}/{name}/run` | Run one turn (`{"message": "...", "session_id": null}`) |

## Build a new agent

```bash
python agent_platform/studio/create_agent.py invoice-helper \
    --description "Extracts and validates invoice fields" \
    --model gemini-2.5-flash

python agent_platform/registry/build_registry.py   # register it
# reload the console — "invoice-helper" is now in the catalog
```

## Deploy

See [`deploy/README.md`](deploy/README.md) — container/Cloud Run for the
gateway, and the existing per-agent Vertex AI Agent Engine path.
