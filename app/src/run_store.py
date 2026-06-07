import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import RUNS_DIR


def _run_fingerprint(run: dict[str, Any]) -> str:
    """Identify identical renders while ignoring timestamps and generated run IDs."""
    comparable = {
        key: value
        for key, value in run.items()
        if key not in {"run_id", "created_at"}
    }
    return json.dumps(comparable, ensure_ascii=False, sort_keys=True)


def save_run(
    model: str,
    selected_tier: str,
    pdf_names: list[str],
    metrics: dict[str, Any],
    result: dict[str, Any],
    case_mode: str = "",
    generated_pdf_path: str = "",
) -> Path:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    recorded_model = str(metrics.get("model") or model)

    extraction_errors = []
    for ext in result.get("extractions", []):
        errs = ext.get("_validation_errors", [])
        if errs:
            extraction_errors.extend(errs)

    analysis_errors = result.get("analysis_validation_errors", [])
    all_valid = len(extraction_errors) == 0 and len(analysis_errors) == 0

    payload = {
        "run_id": run_id,
        "created_at": datetime.now().isoformat(),
        "model": recorded_model,
        "selected_tier": selected_tier,
        "case_mode": case_mode,
        "pdfs": pdf_names,
        "metrics": metrics,
        "validation": {
            "all_valid": all_valid,
            "extraction_errors": extraction_errors,
            "analysis_errors": analysis_errors,
        },
        "generated_pdf_path": generated_pdf_path,
        "result": result,
    }

    out_file = RUNS_DIR / f"{run_id}.json"
    out_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_file


def list_runs() -> list[dict[str, Any]]:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    runs: list[dict[str, Any]] = []
    seen_fingerprints: set[str] = set()
    for file_path in sorted(RUNS_DIR.glob("*.json"), reverse=True):
        try:
            run = json.loads(file_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        fingerprint = _run_fingerprint(run)
        if fingerprint in seen_fingerprints:
            continue
        seen_fingerprints.add(fingerprint)
        runs.append(run)
    return runs
