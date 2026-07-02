import json
from pathlib import Path
import jsonschema
from .config import SCHEMAS_DIR
from .pdf_reader import read_pdf
from .openrouter import OpenRouterClient
from .prompts import build_extraction_prompt, build_analysis_prompt
from .uf_reference import apply_canonical_uf
from .deductible_pricing import enforce_common_deductible
from .metrics import SessionMetrics


def _load_schema(name: str) -> dict:
    path = SCHEMAS_DIR / name
    return json.loads(path.read_text(encoding="utf-8"))


EXTRACTION_SCHEMA_OBJ = _load_schema("extraction.schema.json")
ANALYSIS_SCHEMA_OBJ = _load_schema("analysis.schema.json")


def _parse_json_response(text: str) -> dict:
    """Parse JSON from model response, stripping markdown fences if present."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        start = 1
        end = len(lines)
        for i in range(1, len(lines)):
            if lines[i].strip() == "```":
                end = i
                break
        cleaned = "\n".join(lines[start:end])
    return json.loads(cleaned)


def validate_extraction(data: dict) -> list[str]:
    """Validate extraction JSON against schema. Returns list of errors."""
    errors = []
    try:
        jsonschema.validate(instance=data, schema=EXTRACTION_SCHEMA_OBJ)
    except jsonschema.ValidationError as e:
        errors.append(f"Validation error: {e.message} at {list(e.absolute_path)}")
    except jsonschema.SchemaError as e:
        errors.append(f"Schema error: {e.message}")
    return errors


def validate_analysis(data: dict) -> list[str]:
    """Validate analysis JSON against schema. Returns list of errors."""
    errors = []
    try:
        jsonschema.validate(instance=data, schema=ANALYSIS_SCHEMA_OBJ)
    except jsonschema.ValidationError as e:
        errors.append(f"Validation error: {e.message} at {list(e.absolute_path)}")
    except jsonschema.SchemaError as e:
        errors.append(f"Schema error: {e.message}")
    return errors


def postprocess_hdi_extractions(extractions: list[dict]) -> None:
    """If an extraction is for HDI and contains 11-installment options, filter out other installments."""
    for ext in extractions:
        fields = ext.get("fields", {})
        identity = fields.get("identity", {})
        insurer = (identity.get("insurer_name", {}).get("value") or identity.get("insurer", {}).get("value") or "").lower()
        if "hdi" in insurer:
            pricing_opts = fields.get("pricing_options", [])
            if pricing_opts and isinstance(pricing_opts, list):
                # Check if there's any option with installments == 11
                has_11 = any(isinstance(opt, dict) and opt.get("installments") == 11 for opt in pricing_opts)
                if has_11:
                    # Filter out any options with installments not equal to 11
                    filtered_opts = [
                        opt for opt in pricing_opts
                        if not isinstance(opt, dict) or opt.get("installments") == 11 or opt.get("installments") is None
                    ]
                    fields["pricing_options"] = filtered_opts


class Pipeline:
    """Orchestrates the full extraction + analysis pipeline."""

    def __init__(self, client: OpenRouterClient, session: SessionMetrics, on_step=None):
        self.client = client
        self.session = session
        self.on_step = on_step

    def _notify(self, step_name: str, step_number: int, total: int):
        if self.on_step:
            self.on_step(step_name, step_number, total)

    def run(
        self,
        pdf_paths: list[Path],
        roles: list[str],
        recommended_tier: str = "",
        uf_reference: tuple[float, str] | None = None,
        target_deductible_uf: float | None = None,
    ) -> dict:
        """Run the full pipeline.

        Args:
            pdf_paths: List of PDF paths (policy + quotes)
            roles: List of roles matching each PDF
            recommended_tier: Which tier the broker recommends
            uf_reference: Optional (uf_clp, date_iso) to fix UF
            target_deductible_uf: Optional deductible (UF) to homogenize all offers to,
                using deterministic price-table parsing (see `deductible_pricing.py`)

        Returns:
            Dict with extractions, analysis and validation results
        """
        total_steps = len(pdf_paths) + 1
        extractions = []
        quote_pdf_texts: list[str] = []
        for i, (path, role) in enumerate(zip(pdf_paths, roles)):
            step_name = f"Extrayendo {path.name}"
            self._notify(step_name, i + 1, total_steps)

            pdf_data = read_pdf(path)
            doc_type = "current_policy" if role == "current_policy" else "quote"
            if role != "current_policy":
                quote_pdf_texts.append(pdf_data["text"])
            messages = build_extraction_prompt(
                pdf_text=pdf_data["text"],
                file_name=pdf_data["file_name"],
                document_type=doc_type,
                document_role=role,
            )
            response_text, call_metrics = self.client.chat(
                messages=messages,
                step_name=f"extraction_{i + 1}",
            )
            self.session.add_call(call_metrics)

            try:
                extraction = _parse_json_response(response_text)
            except json.JSONDecodeError:
                extraction = {"error": "Failed to parse JSON", "raw": response_text[:500]}

            extraction["_validation_errors"] = validate_extraction(extraction)
            extractions.append(extraction)

        analysis_step = len(pdf_paths) + 1
        total_all = analysis_step
        self._notify("Analizando caso completo", analysis_step, total_all)

        clean_extractions = []
        for ext in extractions:
            clean = {k: v for k, v in ext.items() if k != "_validation_errors"}
            clean_extractions.append(clean)

        postprocess_hdi_extractions(clean_extractions)

        uf_clp: float | None = None
        uf_date: str | None = None
        if uf_reference is not None:
            uf_clp, uf_date = uf_reference[0], uf_reference[1]

        messages = build_analysis_prompt(
            clean_extractions,
            recommended_tier,
            uf_clp=uf_clp,
            uf_date=uf_date,
        )
        response_text, call_metrics = self.client.chat(
            messages=messages,
            step_name="analysis",
        )
        self.session.add_call(call_metrics)

        try:
            analysis = _parse_json_response(response_text)
        except json.JSONDecodeError:
            analysis = {"error": "Failed to parse JSON", "raw": response_text[:500]}

        if (
            uf_reference is not None
            and isinstance(analysis, dict)
            and analysis.get("error") is None
        ):
            apply_canonical_uf(analysis, uf_reference[0], uf_reference[1])

        if (
            target_deductible_uf is not None
            and isinstance(analysis, dict)
            and analysis.get("error") is None
        ):
            enforce_common_deductible(analysis, quote_pdf_texts, target_deductible_uf)

        analysis_errors = validate_analysis(analysis)

        result = {
            "extractions": extractions,
            "analysis": analysis,
            "analysis_validation_errors": analysis_errors,
        }

        return result
