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

"""Studio: scaffold a new ADK agent from a template (build-your-own-agent).

Usage:
  python agent_platform/studio/create_agent.py my-cool-agent \
      --description "Does cool things" --model gemini-2.5-flash

Creates python/agents/my-cool-agent/ following the repo convention so it is
picked up automatically by the registry on the next build.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"


def _pkg_name(slug: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", slug.lower()).strip("_")


def scaffold(slug: str, description: str, model: str) -> Path:
    slug = slug.strip().lower()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", slug):
        raise SystemExit(f"Invalid agent name '{slug}'. Use lowercase, digits, hyphens.")

    pkg = _pkg_name(slug)
    agent_dir = REPO_ROOT / "python" / "agents" / slug
    if agent_dir.exists():
        raise SystemExit(f"Agent already exists: {agent_dir}")

    pkg_dir = agent_dir / pkg
    pkg_dir.mkdir(parents=True)

    subs = {"slug": slug, "pkg": pkg, "description": description, "model": model}
    for tmpl in TEMPLATE_DIR.glob("*.tmpl"):
        target_name = tmpl.stem.replace("PKG", pkg)  # e.g. PKG__agent.py -> <pkg>/agent.py
        content = tmpl.read_text(encoding="utf-8").format(**subs)
        if target_name.endswith("__agent.py") or target_name.endswith("__prompt.py") or target_name.endswith("____init__.py"):
            fname = target_name.split("__", 1)[1]
            (pkg_dir / fname).write_text(content, encoding="utf-8")
        else:
            (agent_dir / target_name).write_text(content, encoding="utf-8")

    return agent_dir


def main() -> int:
    ap = argparse.ArgumentParser(description="Scaffold a new ADK agent.")
    ap.add_argument("name", help="agent slug, e.g. 'invoice-helper'")
    ap.add_argument("--description", default="A new ADK agent.", help="one-line description")
    ap.add_argument("--model", default="gemini-2.5-flash", help="Gemini model id")
    args = ap.parse_args()

    agent_dir = scaffold(args.name, args.description, args.model)
    rel = agent_dir.relative_to(REPO_ROOT)
    print(f"Created agent scaffold at {rel}")
    print("Next steps:")
    print(f"  1. Edit {rel}/{_pkg_name(args.name)}/prompt.py and agent.py")
    print("  2. python agent_platform/registry/build_registry.py   # register it")
    print("  3. Reload the console; your agent appears in the catalog.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
