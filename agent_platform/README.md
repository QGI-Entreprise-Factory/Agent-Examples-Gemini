# ADK Agent Platform

Turns this repo's collection of **80+ standalone ADK sample agents** into a
single, runnable **agent AI platform**: discover every agent, browse them in a
web console, **chat with token streaming (SSE)**, drive everything from a
**CLI**, scaffold new agents, and deploy.

It is **additive and non-invasive** — no sample agent is modified. The platform
keys off the existing ADK `root_agent` convention, so new samples appear
automatically. A credential-free **builtin echo agent** lets the full
request → runner → SSE → response loop be tested end to end with **no GCP
credentials and no network**.

> See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the design and roadmap.

## Layers

| Layer | Path | What it does |
|-------|------|--------------|
| Registry | `registry/build_registry.py` | Scans the repo → `agents.json` (offline) |
| API Gateway | `backend/app.py` | FastAPI: list / detail / run / **stream (SSE)** |
| Web Console | `frontend/index.html` | Browse, filter, chat with live streaming |
| CLI | `cli.py` (`agp`) | Drive the whole platform from the terminal |
| Studio | `studio/create_agent.py` | Scaffold a new agent from a template |
| Builtin agent | `builtin_agents/echo/` | Credential-free agent for e2e tests/demos |
| Deploy | `deploy/` | Containerize the gateway; per-agent → Vertex |

## Quickstart (CLI-first)

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r agent_platform/backend/requirements.txt

# Everything runs through the `agp` CLI (python -m agent_platform):
python -m agent_platform doctor              # environment / readiness check
python -m agent_platform registry build      # scan repo -> agents.json
python -m agent_platform agents list -l builtin
python -m agent_platform agents run builtin/echo "hello"   # no creds needed
python -m agent_platform serve               # gateway + console at :8000
```

Open <http://localhost:8000> for the console.

The **catalog, search, detail, and the builtin echo agent work immediately**
with no credentials. To run a *cloud* sample agent, configure the GCP/Vertex
credentials that agent's `.env.example` describes.

## API

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/api/health` | Status + agent count + execution availability |
| `GET` | `/api/agents?language=&category=&q=` | List / filter the catalog |
| `GET` | `/api/agents/{language}/{name}` | Agent detail + README |
| `POST`| `/api/agents/{language}/{name}/run` | Run one turn (buffered) |
| `POST`| `/api/agents/{language}/{name}/stream` | Run one turn, **SSE token stream** |

## Build a new agent

```bash
python -m agent_platform new invoice-helper \
    -d "Extracts and validates invoice fields" -m gemini-2.5-flash
# scaffolds python/agents/invoice-helper/, registers it; reload the console.
```

## Tests

```bash
python -m agent_platform test          # light tests (no creds)
python -m agent_platform test --e2e    # full e2e via builtin/echo agent
```

## Deploy

See [`deploy/README.md`](deploy/README.md) — container/Cloud Run for the
gateway, and the existing per-agent Vertex AI Agent Engine path.
