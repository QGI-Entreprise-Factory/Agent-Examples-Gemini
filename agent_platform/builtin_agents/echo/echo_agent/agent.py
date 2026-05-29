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

"""A credential-free ADK agent used for platform end-to-end testing.

This is a *real* ADK ``BaseAgent`` driven through the real ``Runner`` — it just
does not call an LLM, so it runs anywhere with no GCP/Vertex credentials and no
network. It streams a few partial chunks then a final aggregated response,
mirroring the SSE token-streaming shape of LLM agents so the platform's
streaming path is genuinely exercised end to end.
"""

from __future__ import annotations

from typing import AsyncGenerator

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.genai import types


class EchoAgent(BaseAgent):
    """Streams back the user's last message in deterministic chunks."""

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        user_text = _latest_user_text(ctx)
        reply = f"echo: {user_text}" if user_text else "echo: (no message)"

        # Stream partial chunks (word by word) like an LLM would.
        words = reply.split(" ")
        for i, word in enumerate(words[:-1]):
            yield Event(
                author=self.name,
                partial=True,
                content=types.Content(
                    role="model", parts=[types.Part(text=word + " ")]
                ),
            )
        # Final aggregated response (partial defaults to False -> is_final).
        yield Event(
            author=self.name,
            turn_complete=True,
            content=types.Content(role="model", parts=[types.Part(text=reply)]),
        )


def _latest_user_text(ctx: InvocationContext) -> str:
    """Pull the most recent user message text from the session history."""
    try:
        events = ctx.session.events or []
    except AttributeError:
        events = []
    for event in reversed(events):
        content = getattr(event, "content", None)
        if content and getattr(content, "role", None) == "user" and content.parts:
            return "".join(p.text for p in content.parts if getattr(p, "text", None))
    # Fallback: the live user content on the invocation context.
    uc = getattr(ctx, "user_content", None)
    if uc and getattr(uc, "parts", None):
        return "".join(p.text for p in uc.parts if getattr(p, "text", None))
    return ""


root_agent = EchoAgent(
    name="echo",
    description="Credential-free echo agent for platform e2e testing.",
)
