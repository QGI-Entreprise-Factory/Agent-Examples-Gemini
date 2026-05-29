# platform-echo

A credential-free ADK agent used by the platform's end-to-end tests and demos.

It is a real `BaseAgent` run through the real `Runner`, but it does not call an
LLM — so it works with **no GCP/Vertex credentials and no network**. It streams
partial chunks then a final aggregated response, mirroring the SSE shape of LLM
agents so the platform's streaming path is genuinely exercised.

This lets `agp test` validate the full request → runner → SSE → response loop
in CI without any cloud setup.
