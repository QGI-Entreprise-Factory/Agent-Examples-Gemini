# Copyright 2025 Google LLC
# Licensed under the Apache License, Version 2.0.
#
# Container image for the ADK Agent Platform API gateway + web console.
# Build from the REPO ROOT so the sample agents are available for execution:
#   docker build -f agent_platform/deploy/Dockerfile -t adk-platform .
#   docker run -p 8000:8000 adk-platform

FROM python:3.11-slim

WORKDIR /app

# Gateway deps (and optional google-adk for execution).
COPY agent_platform/backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy the platform layer and the sample agents it serves.
COPY agent_platform /app/agent_platform
COPY python /app/python
COPY typescript /app/typescript
COPY go /app/go
COPY java /app/java

# Pre-build the registry manifest at image-build time.
RUN python /app/agent_platform/registry/build_registry.py

EXPOSE 8000
ENV PORT=8000
CMD ["sh", "-c", "uvicorn agent_platform.backend.app:app --host 0.0.0.0 --port ${PORT}"]
