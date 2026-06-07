import json
import time
import threading
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, IntPrompt
from rich.live import Live
from rich.layout import Layout
from rich.text import Text
from .config import AVAILABLE_MODELS, RUNS_DIR
from .metrics import SessionMetrics


console = Console()


def select_model() -> str:
    """Show model selection menu and return chosen model ID."""
    console.print("\n[bold]Modelos disponibles:[/bold]\n")
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("N", style="cyan", width=4)
    table.add_column("Modelo")
    for i, model in enumerate(AVAILABLE_MODELS, 1):
        table.add_row(str(i), model)
    console.print(table)
    console.print()

    while True:
        choice = IntPrompt.ask(
            "[bold]Elige un modelo (número)[/bold]",
            default=1,
        )
        if 1 <= choice <= len(AVAILABLE_MODELS):
            selected = AVAILABLE_MODELS[choice - 1]
            console.print(f"\n  Modelo seleccionado: [bold green]{selected}[/bold green]\n")
            return selected
        console.print("[red]Número inválido, intenta de nuevo.[/red]")


def select_pdfs() -> list[Path]:
    """Ask for a folder path and return PDF files found."""
    folder = Prompt.ask(
        "[bold]Ruta a la carpeta con los PDFs[/bold]",
        default="samples",
    )
    folder_path = Path(folder).expanduser()
    if not folder_path.is_absolute():
        from .config import BASE_DIR
        folder_path = BASE_DIR / folder

    if not folder_path.exists():
        console.print(f"[red]La carpeta no existe: {folder_path}[/red]")
        return []

    pdfs = sorted(folder_path.glob("*.pdf"))
    if not pdfs:
        console.print(f"[red]No se encontraron PDFs en: {folder_path}[/red]")
        return []

    console.print(f"\n[bold]PDFs encontrados ({len(pdfs)}):[/bold]\n")
    for i, p in enumerate(pdfs, 1):
        console.print(f"  {i}. {p.name}")
    console.print()
    return pdfs


def assign_roles(pdfs: list[Path]) -> list[str]:
    """Let user assign roles to each PDF."""
    roles_options = ["current_policy", "initial_option", "middle_option", "pro_option"]
    console.print("[bold]Asigna un rol a cada PDF:[/bold]\n")
    console.print("  1. current_policy  (póliza actual)")
    console.print("  2. initial_option  (cotización barata)")
    console.print("  3. middle_option   (cotización media)")
    console.print("  4. pro_option      (cotización cara)")
    console.print()

    roles = []
    for pdf in pdfs:
        while True:
            choice = IntPrompt.ask(f"  Rol para [cyan]{pdf.name}[/cyan]", default=len(roles) + 1)
            if 1 <= choice <= 4:
                roles.append(roles_options[choice - 1])
                break
            console.print("  [red]Elige entre 1 y 4[/red]")
    return roles


def show_live_metrics(session: SessionMetrics, stop_event: threading.Event):
    """Display live updating metrics panel."""
    with Live(console=console, refresh_per_second=2) as live:
        while not stop_event.is_set():
            elapsed = session.elapsed()
            panel_text = (
                f"[bold]Tiempo:[/bold]       {elapsed:>7.1f}s\n"
                f"[bold]Tokens in:[/bold]    {session.total_tokens_in:>7,}\n"
                f"[bold]Tokens out:[/bold]   {session.total_tokens_out:>7,}\n"
                f"[bold]Costo:[/bold]        ${session.total_cost_usd:>9.6f} USD\n"
                f"[bold]Llamadas:[/bold]     {len(session.calls):>7}"
            )
            panel = Panel(
                panel_text,
                title="[bold yellow]Ejecución en curso[/bold yellow]",
                border_style="yellow",
            )
            live.update(panel)
            time.sleep(0.5)


def show_final_summary(session: SessionMetrics):
    """Display final execution summary."""
    console.print()
    table = Table(title="Resumen de Ejecución", border_style="green")
    table.add_column("Métrica", style="bold")
    table.add_column("Valor", justify="right")

    table.add_row("Modelo", session.model)
    table.add_row("Tiempo total", f"{session.total_time_seconds:.1f}s")
    table.add_row("Tokens entrada", f"{session.total_tokens_in:,}")
    table.add_row("Tokens salida", f"{session.total_tokens_out:,}")
    table.add_row("Costo total", f"${session.total_cost_usd:.6f} USD")
    table.add_row("Llamadas al modelo", str(len(session.calls)))
    console.print(table)

    console.print("\n[bold]Detalle por llamada:[/bold]\n")
    detail_table = Table(box=None, padding=(0, 1))
    detail_table.add_column("#", style="dim", width=3)
    detail_table.add_column("Paso")
    detail_table.add_column("Tiempo", justify="right")
    detail_table.add_column("Tokens in", justify="right")
    detail_table.add_column("Tokens out", justify="right")
    detail_table.add_column("Costo", justify="right")

    for i, call in enumerate(session.calls, 1):
        detail_table.add_row(
            str(i),
            call.step,
            f"{call.time_seconds:.1f}s",
            f"{call.tokens_in:,}",
            f"{call.tokens_out:,}",
            f"${call.cost_usd:.6f}",
        )
    console.print(detail_table)
    console.print()


def show_runs_history():
    """Display history of past runs for comparison."""
    runs_dir = RUNS_DIR
    if not runs_dir.exists():
        console.print("[yellow]No hay ejecuciones guardadas aún.[/yellow]")
        return

    run_files = sorted(runs_dir.glob("*.json"), reverse=True)
    if not run_files:
        console.print("[yellow]No hay ejecuciones guardadas aún.[/yellow]")
        return

    table = Table(title="Historial de Ejecuciones", border_style="blue")
    table.add_column("Run ID", style="dim")
    table.add_column("Modelo")
    table.add_column("Tiempo", justify="right")
    table.add_column("Tokens (in/out)", justify="right")
    table.add_column("Costo USD", justify="right")
    table.add_column("Schema OK", justify="center")

    for rf in run_files[:20]:
        try:
            data = json.loads(rf.read_text(encoding="utf-8"))
            metrics = data.get("metrics", {})
            validation = data.get("validation", {})
            schema_ok = "Si" if validation.get("all_valid", False) else "No"
            table.add_row(
                data.get("run_id", rf.stem),
                metrics.get("model", "?"),
                f"{metrics.get('total_time_seconds', 0):.1f}s",
                f"{metrics.get('total_tokens_in', 0):,} / {metrics.get('total_tokens_out', 0):,}",
                f"${metrics.get('total_cost_usd', 0):.6f}",
                schema_ok,
            )
        except (json.JSONDecodeError, KeyError):
            continue

    console.print(table)
    console.print()


def show_comparison_table():
    """Show a comparison table grouped by model."""
    runs_dir = RUNS_DIR
    if not runs_dir.exists():
        console.print("[yellow]No hay ejecuciones guardadas.[/yellow]")
        return

    run_files = sorted(runs_dir.glob("*.json"))
    if not run_files:
        console.print("[yellow]No hay ejecuciones guardadas.[/yellow]")
        return

    by_model: dict[str, list] = {}
    for rf in run_files:
        try:
            data = json.loads(rf.read_text(encoding="utf-8"))
            model = data.get("metrics", {}).get("model", "unknown")
            by_model.setdefault(model, []).append(data)
        except (json.JSONDecodeError, KeyError):
            continue

    table = Table(title="Comparación por Modelo", border_style="magenta")
    table.add_column("Modelo")
    table.add_column("Runs", justify="right")
    table.add_column("Tiempo prom.", justify="right")
    table.add_column("Tokens prom.", justify="right")
    table.add_column("Costo prom.", justify="right")

    for model, runs in sorted(by_model.items()):
        n = len(runs)
        avg_time = sum(r["metrics"]["total_time_seconds"] for r in runs) / n
        avg_tokens = sum(
            r["metrics"]["total_tokens_in"] + r["metrics"]["total_tokens_out"]
            for r in runs
        ) / n
        avg_cost = sum(r["metrics"]["total_cost_usd"] for r in runs) / n
        table.add_row(
            model,
            str(n),
            f"{avg_time:.1f}s",
            f"{avg_tokens:,.0f}",
            f"${avg_cost:.6f}",
        )

    console.print(table)
    console.print()
