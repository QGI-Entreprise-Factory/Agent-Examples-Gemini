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

"""Discover every ADK sample agent in the repo and emit a registry manifest.

The repo follows a stable convention:
  <lang>/agents/<agent-dir>/<package>/agent.py  ->  exports `root_agent`
  <lang>/agents/<agent-dir>/pyproject.toml      ->  name + description
  <lang>/agents/<agent-dir>/README.md           ->  human docs

This script scans that layout and writes `agents.json`, the single source of
truth the API gateway and web console read. It runs fully offline -- no GCP
credentials, no `google-adk`, no network needed.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

try:  # Python 3.11+ stdlib; fall back to the third-party shim if needed.
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

# platform/registry/build_registry.py -> repo root is three levels up.
REPO_ROOT = Path(__file__).resolve().parents[2]
LANGUAGES = ("python", "typescript", "go", "java")
# Platform-provided agents (e.g. the credential-free echo agent for e2e).
BUILTIN_ROOT = Path(__file__).resolve().parents[1] / "builtin_agents"
OUTPUT = Path(__file__).resolve().parent / "agents.json"


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _read_readme_title(agent_dir: Path) -> str | None:
    readme = agent_dir / "README.md"
    if not readme.exists():
        return None
    for line in readme.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
    return None


def _read_readme_summary(agent_dir: Path) -> str | None:
    readme = agent_dir / "README.md"
    if not readme.exists():
        return None
    in_body = False
    for line in readme.read_text(encoding="utf-8", errors="ignore").splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            in_body = True
            continue
        if in_body and stripped and not stripped.startswith(("#", "!", "[", ">", "```")):
            return stripped
    return None


def _read_pyproject(agent_dir: Path) -> dict:
    pyproject = agent_dir / "pyproject.toml"
    if not pyproject.exists():
        return {}
    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 - malformed sample shouldn't kill the scan
        return {}
    return data.get("project", {})


def _find_python_module(agent_dir: Path) -> str | None:
    """Return the import path (relative to agent_dir) whose package exports root_agent."""
    for agent_py in sorted(agent_dir.rglob("agent.py")):
        # Skip nested sub_agents; we want the top-level package agent.py.
        rel = agent_py.relative_to(agent_dir)
        if "sub_agents" in rel.parts:
            continue
        text = agent_py.read_text(encoding="utf-8", errors="ignore")
        if "root_agent" not in text:
            continue
        # package dir holding agent.py (everything above the file)
        package = ".".join(rel.parts[:-1]) if len(rel.parts) > 1 else None
        return package or rel.parts[0].replace(".py", "")
    return None


def _categorize(name: str, description: str) -> str:
    text = f"{name} {description}".lower()
    buckets = {
        "research": ["research", "academic", "search", "trends", "fomc", "economic"],
        "finance": ["financial", "payment", "loan", "invoice", "kyc", "insurance", "advisor"],
        "data": ["data", "engineering", "science", "forecasting", "machine-learning", "bigquery"],
        "media": ["media", "movie", "image", "brand", "marketing", "presentation", "blog", "story"],
        "ops": ["incident", "bug", "observability", "supply-chain", "airflow", "sdlc", "order"],
        "customer": ["customer", "service", "shopping", "concierge", "expense"],
        "healthcare": ["medical", "nurse", "claim", "pre-authorization", "handover"],
        "security": ["security", "guardian", "cyber", "auditor", "safety"],
    }
    for category, keywords in buckets.items():
        if any(k in text for k in keywords):
            return category
    return "general"


def _build_entry(agent_dir: Path, lang: str) -> dict:
    """Build one manifest entry for an agent directory."""
    project = _read_pyproject(agent_dir)
    name = project.get("name") or _read_readme_title(agent_dir) or agent_dir.name
    description = (
        project.get("description") or _read_readme_summary(agent_dir) or ""
    )
    entry = {
        "id": f"{lang}/{agent_dir.name}",
        "slug": _slugify(agent_dir.name),
        "name": name,
        "description": description.strip(),
        "language": lang,
        "path": str(agent_dir.relative_to(REPO_ROOT)),
        "category": _categorize(agent_dir.name, description),
        "has_readme": (agent_dir / "README.md").exists(),
        "deployable": (agent_dir / "deployment").is_dir(),
        "builtin": lang == "builtin",
    }
    if lang in ("python", "builtin"):
        entry["module"] = _find_python_module(agent_dir)
        entry["runnable"] = entry["module"] is not None
    else:
        entry["module"] = None
        entry["runnable"] = False
    return entry


def discover() -> list[dict]:
    agents: list[dict] = []
    # Platform builtin agents first (credential-free, always runnable).
    if BUILTIN_ROOT.is_dir():
        for agent_dir in sorted(p for p in BUILTIN_ROOT.iterdir() if p.is_dir()):
            if agent_dir.name.startswith((".", "_")):
                continue
            agents.append(_build_entry(agent_dir, "builtin"))
    for lang in LANGUAGES:
        agents_root = REPO_ROOT / lang / "agents"
        if not agents_root.is_dir():
            continue
        for agent_dir in sorted(p for p in agents_root.iterdir() if p.is_dir()):
            if agent_dir.name.startswith((".", "_")):
                continue
            agents.append(_build_entry(agent_dir, lang))
    return agents


def main() -> int:
    agents = discover()
    manifest = {
        "version": 1,
        "agent_count": len(agents),
        "languages": sorted({a["language"] for a in agents}),
        "categories": sorted({a["category"] for a in agents}),
        "agents": agents,
    }
    OUTPUT.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    runnable = sum(1 for a in agents if a["runnable"])
    print(f"Discovered {len(agents)} agents ({runnable} python-runnable).")
    print(f"Wrote manifest -> {OUTPUT.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
