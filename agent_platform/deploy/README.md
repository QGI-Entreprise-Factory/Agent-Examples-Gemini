# Deploying the ADK Agent Platform

Two distinct deployment concerns:

## 1. The platform gateway (this layer)

The FastAPI gateway + web console can be containerized and deployed anywhere
that runs a container.

### Local container

```bash
# from the repo root
docker build -f agent_platform/deploy/Dockerfile -t adk-platform .
docker run -p 8000:8000 adk-platform
# open http://localhost:8000
```

### Cloud Run

```bash
gcloud run deploy adk-platform \
  --source . \
  --dockerfile agent_platform/deploy/Dockerfile \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars GOOGLE_CLOUD_PROJECT=$PROJECT,GOOGLE_GENAI_USE_VERTEXAI=True
```

For agent **execution** (the `/run` endpoint) the service account needs Vertex
AI access (`roles/aiplatform.user`). Without it, the catalog and detail views
still work; only execution returns `503`.

## 2. Individual agents (Vertex AI Agent Engine)

Each runnable sample with a `deployment/` directory ships its own
`deploy.py` that pushes that single agent to **Vertex AI Agent Engine** as a
managed, autoscaling endpoint. The platform registry marks these with
`"deployable": true`.

```bash
cd python/agents/<agent>
uv sync
python deployment/deploy.py --create
```

This is the production path for serving one agent at scale; the gateway above
is the unified front door for discovery, multi-agent routing, and the console.
