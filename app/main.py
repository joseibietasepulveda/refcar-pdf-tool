#!/usr/bin/env python3
"""Herramienta de Seguros - Comparador de Modelos.

App local para extraer datos de PDFs de cotizaciones de seguros automotrices
y comparar el rendimiento de distintos modelos LLM via OpenRouter.
"""

import json
import threading
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, IntPrompt

from src.config import OPENROUTER_API_KEY, RUNS_DIR
from src.openrouter import OpenRouterClient
from src.metrics import SessionMetrics
from src.pipeline import Pipeline
from src.uf_reference import resolve_reference_uf
from src.display import (
    console,
    select_model,
    select_pdfs,
    assign_roles,
    show_live_metrics,
    show_final_summary,
    show_runs_history,
    show_comparison_table,
)


def save_run(session: SessionMetrics, result: dict, pdfs: list[Path]) -> Path:
    """Save execution results to a JSON file."""
    RUNS_DIR.mkdir(parents=True, exist_ok=True)

    run_id = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    extraction_errors = []
    for ext in result.get("extractions", []):
        errs = ext.pop("_validation_errors", [])
        if errs:
            extraction_errors.extend(errs)

    all_valid = (
        len(extraction_errors) == 0
        and len(result.get("analysis_validation_errors", [])) == 0
    )

    run_data = {
        "run_id": run_id,
        "pdfs": [p.name for p in pdfs],
        "metrics": session.to_dict(),
        "result": result,
        "validation": {
            "all_valid": all_valid,
            "extraction_errors": extraction_errors,
            "analysis_errors": result.get("analysis_validation_errors", []),
        },
    }

    out_path = RUNS_DIR / f"{run_id}.json"
    out_path.write_text(json.dumps(run_data, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path


def run_extraction(model: str, pdfs: list[Path], roles: list[str]):
    """Execute the full extraction pipeline with live metrics."""
    session = SessionMetrics(model=model)

    client = OpenRouterClient(model=model)
    console.print("[dim]Obteniendo precios de modelos...[/dim]")
    client.fetch_model_prices()

    pipeline = Pipeline(
        client=client,
        session=session,
        on_step=lambda name, n, total: console.print(
            f"  [cyan][{n}/{total}][/cyan] {name}"
        ),
    )

    session.start_timer()

    stop_event = threading.Event()
    metrics_thread = threading.Thread(
        target=show_live_metrics,
        args=(session, stop_event),
        daemon=True,
    )
    metrics_thread.start()

    try:
        uf_ref = resolve_reference_uf(
            manual_clp=None,
            manual_date=None,
            fetch_online=True,
        )
        result = pipeline.run(
            pdf_paths=pdfs,
            roles=roles,
            recommended_tier="middle_option",
            uf_reference=uf_ref,
        )
    finally:
        stop_event.set()
        metrics_thread.join(timeout=2)
        client.close()

    show_final_summary(session)

    out_path = save_run(session, result, pdfs)
    console.print(f"[green]Resultado guardado en:[/green] {out_path}\n")

    return result


def main_menu():
    """Main application loop."""
    console.print(
        Panel(
            "[bold]HERRAMIENTA SEGUROS[/bold]\n"
            "Extracción de PDFs + Comparador de Modelos\n\n"
            "[dim]Conecta a OpenRouter para testear distintos LLMs[/dim]",
            border_style="blue",
        )
    )

    if not OPENROUTER_API_KEY:
        console.print(
            "[bold red]ERROR:[/bold red] No se encontró OPENROUTER_API_KEY.\n"
            "Crea un archivo .env con tu API key. Ver .env.example\n"
        )
        return

    while True:
        console.print("[bold]Menu principal:[/bold]\n")
        console.print("  [cyan]1.[/cyan] Ejecutar extracción (subir PDFs + elegir modelo)")
        console.print("  [cyan]2.[/cyan] Ver historial de ejecuciones")
        console.print("  [cyan]3.[/cyan] Comparar modelos")
        console.print("  [cyan]4.[/cyan] Salir")
        console.print()

        choice = IntPrompt.ask("[bold]Opción[/bold]", default=1)

        if choice == 1:
            model = select_model()
            pdfs = select_pdfs()
            if not pdfs:
                continue
            roles = assign_roles(pdfs)
            run_extraction(model, pdfs, roles)

        elif choice == 2:
            show_runs_history()

        elif choice == 3:
            show_comparison_table()

        elif choice == 4:
            console.print("[dim]Hasta luego.[/dim]")
            break

        else:
            console.print("[red]Opción no válida.[/red]\n")


if __name__ == "__main__":
    main_menu()
