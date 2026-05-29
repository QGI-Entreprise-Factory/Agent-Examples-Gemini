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

"""Dynamically loads a sample agent's `root_agent` and runs turns via the ADK.

Execution requires `google-adk` to be installed and (for most agents) GCP /
Vertex credentials configured in the agent's environment. When those are
missing this module raises `AgentExecutionError` with an actionable message so
the gateway can degrade gracefully -- the catalog stays usable either way.
"""

from __future__ import annotations

import importlib
import sys
from functools import lru_cache
from pathlib import Path

from . import registry

REPO_ROOT = registry.REPO_ROOT


class AgentExecutionError(RuntimeError):
    """Raised when an agent cannot be imported or run."""


def adk_available() -> bool:
    try:
        importlib.import_module("google.adk")
        return True
    except Exception:  # noqa: BLE001
        return False


@lru_cache(maxsize=64)
def load_root_agent(agent_id: str):
    """Import the sample package and return its `root_agent` object."""
    meta = registry.get_agent(agent_id)
    if meta is None:
        raise AgentExecutionError(f"Unknown agent: {agent_id}")
    if meta["language"] not in ("python", "builtin"):
        raise AgentExecutionError(
            f"{agent_id} is a {meta['language']} agent; the runner currently "
            "executes Python and builtin agents only."
        )
    module_path = meta.get("module")
    if not module_path:
        raise AgentExecutionError(f"{agent_id} does not export a root_agent module.")

    agent_dir = REPO_ROOT / meta["path"]
    if str(agent_dir) not in sys.path:
        sys.path.insert(0, str(agent_dir))
    try:
        module = importlib.import_module(f"{module_path}.agent")
    except ModuleNotFoundError:
        module = importlib.import_module(module_path)
    except Exception as exc:  # noqa: BLE001
        raise AgentExecutionError(f"Failed to import {agent_id}: {exc}") from exc

    root_agent = getattr(module, "root_agent", None)
    if root_agent is None:
        raise AgentExecutionError(f"{agent_id} module has no `root_agent`.")
    return root_agent


class AgentSession:
    """Wraps an ADK Runner + in-memory session for a single conversation."""

    def __init__(self, agent_id: str, user_id: str = "platform-user"):
        if not adk_available():
            raise AgentExecutionError(
                "google-adk is not installed. Install backend/requirements.txt to "
                "enable agent execution; the catalog works without it."
            )
        from google.adk.runners import InMemoryRunner  # local import: optional dep

        self.agent_id = agent_id
        self.user_id = user_id
        root_agent = load_root_agent(agent_id)
        self._runner = InMemoryRunner(agent=root_agent, app_name=agent_id)
        self._session = None

    async def _ensure_session(self):
        if self._session is None:
            self._session = await self._runner.session_service.create_session(
                app_name=self.agent_id, user_id=self.user_id
            )
        return self._session

    async def stream(self, message: str):
        """Send a user turn; yield normalized event dicts as they arrive."""
        from google.genai import types  # local import: optional dep

        session = await self._ensure_session()
        content = types.Content(role="user", parts=[types.Part(text=message)])
        async for event in self._runner.run_async(
            user_id=self.user_id,
            session_id=session.id,
            new_message=content,
        ):
            yield _normalize_event(event)

    async def send(self, message: str) -> list[dict]:
        """Send a user turn; return all of the agent's event responses."""
        return [event async for event in self.stream(message)]


def _normalize_event(event) -> dict:
    text_parts = []
    if getattr(event, "content", None) and event.content.parts:
        text_parts = [p.text for p in event.content.parts if getattr(p, "text", None)]
    is_final = (
        event.is_final_response()
        if hasattr(event, "is_final_response")
        else not getattr(event, "partial", False)
    )
    return {
        "author": getattr(event, "author", "agent"),
        "text": "".join(text_parts),
        "partial": bool(getattr(event, "partial", False)),
        "is_final": bool(is_final),
    }
