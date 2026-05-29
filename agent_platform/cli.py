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

"""``agp`` — the ADK Agent Platform command-line interface.

A single entry point for every platform operation:

    agp doctor                      environment / readiness check
    agp registry build              (re)scan the repo -> agents.json
    agp agents list [--lang ...]    browse the catalog
    agp agents show <id>            agent detail
    agp agents run <id> "<msg>"     run an agent turn (streams to stdout)
    agp serve [--port 8000]         start the gateway + web console
    agp new <name> [...]            scaffold a new agent
    agp test [--e2e]                run the platform test suite

CLI-first by design: scripts and CI drive the platform through this tool.
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from .backend import registry, runner
from .registry import build_registry
from .studio import create_agent

REPO_ROOT = registry.REPO_ROOT
console = Console()

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="ADK Agent Platform CLI.",
)
agents_app = typer.Typer(no_args_is_help=True, help="Browse and run agents.")
registry_app = typer.Typer(no_args_is_help=True, help="Manage the agent registry.")
app.add_typer(agents_app, name="agents")
app.add_typer(registry_app, name="registry")


# --------------------------------------------------------------------------- #
# doctor
# --------------------------------------------------------------------------- #
@app.command()
def doctor() -> None:
    """Check the environment and report platform readiness."""
    manifest_exists = registry.MANIFEST.exists()
    adk = runner.adk_available()
    table = Table(title="agp doctor", show_header=False)
    table.add_row("Python", sys.version.split()[0])
    table.add_row("Repo root", str(REPO_ROOT))
    table.add_row("Manifest", "present" if manifest_exists else "[yellow]missing (run: agp registry build)[/]")
    if manifest_exists:
        m = registry.load_manifest()
        table.add_row("Agents", str(m["agent_count"]))
        table.add_row("Runnable", str(sum(1 for a in m["agents"] if a["runnable"])))
    table.add_row("google-adk", "[green]available[/]" if adk else "[yellow]not installed (catalog-only)[/]")
    console.print(table)
    if adk and manifest_exists:
        console.print("[green]Ready.[/] Builtin agents run with no credentials; "
                      "cloud agents need their own GCP/Vertex setup.")


# --------------------------------------------------------------------------- #
# registry
# --------------------------------------------------------------------------- #
@registry_app.command("build")
def registry_build() -> None:
    """Scan the repo and (re)write agents.json."""
    build_registry.main()
    registry.load_manifest.cache_clear()


# --------------------------------------------------------------------------- #
# agents
# --------------------------------------------------------------------------- #
@agents_app.command("list")
def agents_list(
    language: str = typer.Option(None, "--language", "-l", help="filter by language"),
    category: str = typer.Option(None, "--category", "-c", help="filter by category"),
    query: str = typer.Option(None, "--query", "-q", help="search text"),
    runnable_only: bool = typer.Option(False, "--runnable", help="only runnable agents"),
) -> None:
    """List agents in the catalog."""
    items = registry.list_agents(language=language, category=category, query=query)
    if runnable_only:
        items = [a for a in items if a["runnable"]]
    table = Table(title=f"{len(items)} agents")
    table.add_column("id", style="cyan", no_wrap=True)
    table.add_column("lang")
    table.add_column("category")
    table.add_column("run", justify="center")
    table.add_column("description", overflow="fold")
    for a in items:
        table.add_row(
            a["id"], a["language"], a["category"],
            "✓" if a["runnable"] else "·",
            (a["description"] or "")[:70],
        )
    console.print(table)


@agents_app.command("show")
def agents_show(agent_id: str = typer.Argument(..., help="e.g. python/academic-research")) -> None:
    """Show details for one agent."""
    agent = registry.get_agent(agent_id)
    if not agent:
        console.print(f"[red]Agent not found:[/] {agent_id}")
        raise typer.Exit(1)
    for key in ("name", "id", "language", "category", "path", "module", "runnable", "deployable"):
        console.print(f"[bold]{key:11}[/] {agent.get(key)}")
    if agent.get("description"):
        console.print(f"\n{agent['description']}")


@agents_app.command("run")
def agents_run(
    agent_id: str = typer.Argument(..., help="e.g. builtin/echo"),
    message: str = typer.Argument(..., help="the message to send"),
) -> None:
    """Run a single agent turn and stream the response to stdout."""
    async def _run() -> None:
        try:
            session = runner.AgentSession(agent_id)
            console.print(f"[dim]> {message}[/]")
            final = []
            async for ev in session.stream(message):
                if ev["partial"] and ev["text"]:
                    console.print(ev["text"], end="")
                elif ev["is_final"] and ev["text"]:
                    final.append(ev["text"])
            console.print()
            if final:
                console.print(f"[green]{final[-1]}[/]")
        except runner.AgentExecutionError as exc:
            console.print(f"[red]Cannot run:[/] {exc}")
            raise typer.Exit(2)

    asyncio.run(_run())


# --------------------------------------------------------------------------- #
# serve
# --------------------------------------------------------------------------- #
@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", help="bind host"),
    port: int = typer.Option(8000, help="bind port"),
    reload: bool = typer.Option(False, "--reload", help="auto-reload on code change"),
) -> None:
    """Start the API gateway + web console."""
    import uvicorn

    if not registry.MANIFEST.exists():
        build_registry.main()
    console.print(f"[green]Serving[/] http://{host}:{port}  (console + /api)")
    uvicorn.run("agent_platform.backend.app:app", host=host, port=port, reload=reload)


# --------------------------------------------------------------------------- #
# new (studio)
# --------------------------------------------------------------------------- #
@app.command()
def new(
    name: str = typer.Argument(..., help="agent slug, e.g. invoice-helper"),
    description: str = typer.Option("A new ADK agent.", "--description", "-d"),
    model: str = typer.Option("gemini-2.5-flash", "--model", "-m"),
) -> None:
    """Scaffold a new agent and register it."""
    agent_dir = create_agent.scaffold(name, description, model)
    build_registry.main()
    registry.load_manifest.cache_clear()
    console.print(f"[green]Created[/] {agent_dir.relative_to(REPO_ROOT)} and registered it.")


# --------------------------------------------------------------------------- #
# test
# --------------------------------------------------------------------------- #
@app.command()
def test(
    e2e: bool = typer.Option(False, "--e2e", help="include the full e2e suite"),
    verbose: bool = typer.Option(False, "-v", help="verbose output"),
) -> None:
    """Run the platform test suite."""
    cmd = [sys.executable, "-m", "pytest", str(Path(__file__).parent / "tests")]
    if not e2e:
        cmd += ["-m", "not e2e"]
    if verbose:
        cmd.append("-v")
    raise typer.Exit(subprocess.call(cmd, cwd=str(REPO_ROOT)))


def main() -> None:
    app()


if __name__ == "__main__":
    main()
