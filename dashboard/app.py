"""Along Dashboard & Knowledge Base FastAPI Application & CLI Runner."""

import os
import sys
import argparse
import subprocess
import time
import webbrowser
from pathlib import Path
from typing import Optional

try:
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import HTMLResponse, FileResponse
    from fastapi.staticfiles import StaticFiles
    import uvicorn
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

from .core.collector import EntityCollector, find_agents_dir
from .core.watcher import RepoWatcher
from .api.router import api_router
from .api.entities_api import get_collector as entities_get_collector
from .api.kb_api import get_collector as kb_get_collector
from .api.metrics_api import get_collector as metrics_get_collector


def create_app(agents_dir: Path) -> FastAPI:
    """Create and configure the FastAPI application."""
    if not HAS_FASTAPI:
        raise RuntimeError("FastAPI is required to run web server. Run via uv: uv run scripts/along_dash.py --web")

    collector = EntityCollector(agents_dir)
    watcher = RepoWatcher(agents_dir.parent)

    app = FastAPI(
        title="Along Dashboard & Knowledge Base API",
        version="2.2.14",
        description="Type-safe OpenAPI REST & SSE service for Along Protocol entities, dependency DAGs, and Knowledge Base search.",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # Enable CORS for local dev servers (e.g. Vite on 5173)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Store instances in app.state
    app.state.collector = collector
    app.state.watcher = watcher

    # Register API routes
    app.include_router(api_router)

    # Override dependencies
    app.dependency_overrides[entities_get_collector] = lambda: collector
    app.dependency_overrides[kb_get_collector] = lambda: collector
    app.dependency_overrides[metrics_get_collector] = lambda: collector

    # Mount UI static build if present
    ui_dist = Path(__file__).resolve().parent / "ui" / "dist"
    if ui_dist.exists():
        assets_dir = ui_dist / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

        @app.get("/", response_class=HTMLResponse, include_in_schema=False)
        async def serve_ui():
            index_file = ui_dist / "index.html"
            if index_file.exists():
                return FileResponse(str(index_file))
            return HTMLResponse("<h1>Along Dashboard UI bundle not found. Run 'pnpm run build' in packages/dashboard-ui.</h1>")
    else:
        @app.get("/", response_class=HTMLResponse, include_in_schema=False)
        async def serve_fallback_ui():
            collector.collect_all()
            metrics = collector.calculate_metrics()
            return HTMLResponse(f"""
            <!DOCTYPE html>
            <html>
            <head><title>Along Dashboard</title><meta charset="utf-8"></head>
            <body style="font-family: sans-serif; background: #0f172a; color: #f8fafc; padding: 40px;">
                <h1>Along Dashboard (FastAPI Backend)</h1>
                <p>Repository: <b>{collector.repo_root.name}</b></p>
                <p>Completion: <b>{metrics.completion_pct}%</b> ({metrics.done_issues}/{metrics.total_issues} issues done)</p>
                <p><a style="color: #38bdf8;" href="/docs">OpenAPI Swagger UI</a> | <a style="color: #38bdf8;" href="/api/data">JSON API Data</a></p>
                <hr style="border-color: #334155;"/>
                <p><i>To build the React 19 UI: <code>cd packages/dashboard-ui && pnpm run build</code></i></p>
            </body>
            </html>
            """)

    @app.on_event("startup")
    async def startup_event():
        collector.collect_all()

    return app


def create_app_dev() -> FastAPI:
    """Factory for uvicorn --reload in development mode."""
    agents_dir = find_agents_dir(Path.cwd())
    return create_app(agents_dir)


def render_cli(collector: EntityCollector):
    """Render terminal CLI executive summary with Rich or plain text."""
    collector.collect_all()
    m = collector.metrics

    if HAS_RICH:
        console = Console()
        console.print()
        console.print(Panel.fit(
            f"[bold cyan]Along Executive Dashboard[/bold cyan] - [bold white]{collector.repo_root.name}[/bold white]\n"
            f"[dim]Entities path: {collector.agents_dir}[/dim]",
            border_style="cyan"
        ))

        table = Table(title="Project Metrics Summary", show_header=True, header_style="bold magenta")
        table.add_column("Metric", style="dim", width=25)
        table.add_column("Value", justify="right")

        table.add_row("Total Issues", str(m.total_issues))
        table.add_row("Done Issues", f"[green]{m.done_issues}[/green]")
        table.add_row("In Progress Issues", f"[yellow]{m.in_progress_issues}[/yellow]")
        table.add_row("Open Issues", f"[blue]{m.open_issues}[/blue]")
        table.add_row("Blocked Issues", f"[red]{m.blocked_issues}[/red]")
        table.add_row("Completion Rate", f"[bold green]{m.completion_pct}%[/bold green]")
        table.add_row("Active Milestones", str(m.active_milestones))
        table.add_row("Active Risks", f"[red]{m.active_risks}[/red]" if m.active_risks > 0 else "[green]0[/green]")
        table.add_row("Knowledge Base Articles", str(m.total_kb_articles))
        table.add_row("Architectural Decisions", str(m.total_decisions))
        table.add_row("Session Logs", str(m.total_sessions))
        console.print(table)

        # Active issues table
        active_issues = [i for i in collector.issues if i.status in ("in-progress", "open", "blocked")]
        if active_issues:
            i_table = Table(title="Active Issues", show_header=True, header_style="bold blue")
            i_table.add_column("Status", width=12)
            i_table.add_column("Type", width=8)
            i_table.add_column("Priority", width=10)
            i_table.add_column("Title / Key", style="white")

            for iss in active_issues[:15]:
                status_style = "yellow" if iss.status == "in-progress" else ("red" if iss.status == "blocked" else "blue")
                i_table.add_row(
                    f"[{status_style}]{iss.status}[/{status_style}]",
                    iss.type,
                    iss.priority,
                    iss.title or iss.slug
                )
            console.print(i_table)
    else:
        print(f"=== Along Dashboard: {collector.repo_root.name} ===")
        print(f"Total Issues: {m.total_issues} | Done: {m.done_issues} ({m.completion_pct}%) | Active: {m.open_issues + m.in_progress_issues}")
        print(f"Knowledge Base: {m.total_kb_articles} | Decisions: {m.total_decisions} | Risks: {m.active_risks}")


def run_dev_mode(collector: EntityCollector, host: str = "127.0.0.1", port: int = 8765):
    """Run full development mode with Vite HMR frontend (port 5173) and FastAPI backend (port 8765)."""
    ui_dir = collector.repo_root / "packages" / "dashboard-ui"
    vite_url = "http://localhost:5173"
    api_url = f"http://{host}:{port}"

    print("=" * 65)
    print("  Starting Along Dashboard in DEV Mode (Vite HMR + FastAPI API)")
    print("=" * 65)
    print(f"  -> Frontend HMR Dev Server: {vite_url}")
    print(f"  -> Backend FastAPI Service: {api_url}")
    print(f"  -> OpenAPI Swagger UI:     {api_url}/docs")
    print("  Press Ctrl+C to terminate both servers.\n")

    vite_proc = None
    if ui_dir.exists():
        # Check if pnpm is installed
        pnpm_cmd = "pnpm.cmd" if sys.platform == "win32" else "pnpm"
        try:
            vite_proc = subprocess.Popen(
                [pnpm_cmd, "run", "dev"],
                cwd=str(ui_dir),
            )
        except Exception as e:
            print(f"[Warning] Could not start Vite dev server ({e}). Make sure pnpm is installed in PATH.")

    # Open browser to Vite frontend
    time.sleep(1)
    try:
        webbrowser.open(vite_url)
    except Exception:
        pass

    try:
        app = create_app(collector.agents_dir)
        uvicorn.run(app, host=host, port=port, log_level="warning")
    except KeyboardInterrupt:
        print("\nShutting down dev servers...")
    finally:
        if vite_proc:
            vite_proc.terminate()
            try:
                vite_proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                vite_proc.kill()


def main():
    parser = argparse.ArgumentParser(description="Along Dynamic Dashboard & Knowledge Base Engine")
    parser.add_argument("path", nargs="?", default=".", help="Target repository root path (default: .)")
    parser.add_argument("-w", "--web", action="store_true", help="Launch interactive FastAPI web dashboard")
    parser.add_argument("-d", "--dev", action="store_true", help="Launch full development mode (Vite HMR on 5173 + FastAPI on 8765)")
    parser.add_argument("-c", "--cli", action="store_true", help="Print summary table to terminal (default)")
    parser.add_argument("--port", type=int, default=8765, help="Web server port (default: 8765)")
    parser.add_argument("--host", default="127.0.0.1", help="Web server host (default: 127.0.0.1)")
    parser.add_argument("--no-browser", action="store_true", help="Do not open browser automatically")
    parser.add_argument("--export", nargs="?", const=".along/dashboard.html", help="Export standalone static HTML report only when requested")

    args = parser.parse_args()

    agents_dir = find_agents_dir(args.path)
    if not agents_dir.exists():
        print(f"[Error] No .along/ directory found in {args.path} or parent directories.", file=sys.stderr)
        sys.exit(1)

    collector = EntityCollector(agents_dir)

    if args.export:
        out_path = Path(args.export)
        if not out_path.is_absolute():
            out_path = collector.repo_root / out_path
        collector.collect_all()
        full_data_json = collector.to_full_data().model_dump_json(indent=2)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(f"<script>window.__ALONG_DATA__ = {full_data_json};</script>", encoding="utf-8")
        print(f"-> Static dashboard exported: {out_path}")
        return

    if args.dev:
        if not HAS_FASTAPI:
            print("[Error] fastapi and uvicorn are required for dev mode. Run with: uv run scripts/along_dash.py --dev", file=sys.stderr)
            sys.exit(1)
        run_dev_mode(collector, host=args.host, port=args.port)
        return

    if args.web:
        if not HAS_FASTAPI:
            print("[Error] fastapi and uvicorn are required for web mode. Run with: uv run scripts/along_dash.py --web", file=sys.stderr)
            sys.exit(1)

        app = create_app(agents_dir)
        url = f"http://{args.host}:{args.port}"
        print(f"-> Starting Along Dynamic Dashboard & KB API at {url}")
        print(f"   OpenAPI Swagger Documentation: {url}/docs")
        print("   Press Ctrl+C to stop.")

        if not args.no_browser:
            try:
                webbrowser.open(url)
            except Exception:
                pass

        uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
    else:
        render_cli(collector)


if __name__ == "__main__":
    main()
