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

"""Loads and serves the agent registry manifest produced by build_registry.py."""

from __future__ import annotations

import json
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_DIR = REPO_ROOT / "agent_platform" / "registry"
MANIFEST = REGISTRY_DIR / "agents.json"


def _ensure_manifest() -> None:
    """Build the manifest on first run if it has not been generated yet."""
    if MANIFEST.exists():
        return
    subprocess.run(
        [sys.executable, str(REGISTRY_DIR / "build_registry.py")],
        check=True,
        cwd=str(REPO_ROOT),
    )


@lru_cache(maxsize=1)
def load_manifest() -> dict:
    _ensure_manifest()
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def list_agents(
    language: str | None = None,
    category: str | None = None,
    query: str | None = None,
) -> list[dict]:
    agents = load_manifest()["agents"]
    if language:
        agents = [a for a in agents if a["language"] == language]
    if category:
        agents = [a for a in agents if a["category"] == category]
    if query:
        q = query.lower()
        agents = [
            a
            for a in agents
            if q in a["name"].lower() or q in a["description"].lower() or q in a["id"].lower()
        ]
    return agents


def get_agent(agent_id: str) -> dict | None:
    return next((a for a in load_manifest()["agents"] if a["id"] == agent_id), None)


def get_readme(agent_id: str) -> str | None:
    agent = get_agent(agent_id)
    if not agent:
        return None
    readme = REPO_ROOT / agent["path"] / "README.md"
    if not readme.exists():
        return None
    return readme.read_text(encoding="utf-8", errors="ignore")
