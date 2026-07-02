"""PDF generator using HTML template + WeasyPrint.

Receives a JSON conforming to final-render.schema.json and produces
a PDF that matches the fixed commercial layout of the comparative document.
"""

import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

from .config import BASE_DIR

TEMPLATES_DIR = BASE_DIR / "templates"

COLUMN_THEME_BY_POSITION = {
    1: "azul",
    2: "celeste",
    3: "naranja",
    4: "cafe",
}


TIER_DISPLAY_MAP = {
    "initial_option": "BÁSICO",
    "middle_option": "EQUILIBRADO",
    "pro_option": "PRO",
    "initial": "BÁSICO",
    "middle": "EQUILIBRADO",
    "pro": "PRO",
    "intermedia": "EQUILIBRADO",
    "premium": "PRO",
    "estándar": "BÁSICO",
    "estandar": "BÁSICO",
    "básico": "BÁSICO",
    "basico": "BÁSICO",
    "equilibrado": "EQUILIBRADO",
}


def generate_comparative_pdf(render_data: dict, output_path: Path) -> Path:
    """Render the comparative PDF from a final-render JSON payload."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=True)
    template = env.get_template("comparativo.html")

    html_content = template.render(**render_data)
    HTML(string=html_content).write_pdf(str(output_path))

    return output_path


def generate_summary_pdf(
    analysis: dict,
    output_path: Path,
    selected_tier: str,
    offer_tier_overrides: dict[int, str] | None = None,
) -> Path:
    """Build comparative PDF from analysis JSON by transforming it to render format."""
    render_data = _analysis_to_render(analysis, selected_tier, offer_tier_overrides)
    return generate_comparative_pdf(render_data, output_path)


ASSISTANCE_LABEL_BY_CATEGORY = {
    "economica": "Básica",
    "equilibrada": "Equilibrada",
    "premium": "Premium",
}


def _map_tier_to_category_and_badge(raw_tier: str) -> tuple[str, str]:
    """Map a role/tier string to (category, badge_label).

    The three commercial roles a broker can assign (Básico / Equilibrado / Pro)
    always map to the same three labels, regardless of free-text variants that
    the role or the LLM's `commercial_tier` might use (e.g. "ESTÁNDAR",
    "INTERMEDIA", "PREMIUM").
    """
    if not raw_tier:
        return "economica", "OPCIÓN ECONÓMICA"
    raw_lower = raw_tier.strip().lower()
    if any(k in raw_lower for k in ("premium", "pro", "alta")):
        return "premium", "OPCIÓN PREMIUM"
    if any(k in raw_lower for k in ("equilibr", "operacional", "medio", "middle", "intermedia", "intermedio")):
        return "equilibrada", "OPCIÓN EQUILIBRADA"
    return "economica", "OPCIÓN ECONÓMICA"


def _analysis_to_render(
    analysis: dict,
    selected_tier: str,
    offer_tier_overrides: dict[int, str] | None = None,
) -> dict:
    """Transform analysis.schema.json output into final-render template variables."""

    context = analysis.get("context", {})
    insured = analysis.get("insured", {})
    current = analysis.get("current_policy", {})
    offers_raw = analysis.get("offers", [])
    recommendation = analysis.get("recommendation", {})
    footer_config = analysis.get("footer", {})
    broker_name = footer_config.get("broker_name") or "Convision Corredores de Seguros SpA"
    broker_website = footer_config.get("broker_website") or "www.convision.cl"

    vehicle_name = _dv(insured.get("vehicle_display_name")) or (
        f"{_dv(insured.get('vehicle_make'))} {_dv(insured.get('vehicle_model'))} {_dv(insured.get('vehicle_year'))}"
    )

    uf_val = context.get("uf_value_used", 0)
    uf_date = context.get("uf_reference_date", "")

    render_insured = {
        "name": _dv(insured.get("name")),
        "vehicle_display_name": vehicle_name,
        "plate": _dv(insured.get("plate")),
        "usage": _dv(insured.get("usage")),
    }

    has_current = bool(current)
    if has_current:
        current_ded = _dv(current.get("deductible_uf"))
        current_premium_uf = _dv(current.get("monthly_premium_uf"))
        current_premium_clp = _dv(current.get("monthly_premium_clp"))

        render_current = {
            "insurer": _dv(current.get('insurer')),
            "product_name": _dv(current.get('product_name')),
            "header_label": f"{_dv(current.get('insurer'))} {_dv(current.get('product_name'))}".strip(),
            "deductible_label": f"{_fmt_uf(current_ded)} UF",
            "monthly_premium_uf_label": f"UF {_fmt_uf(current_premium_uf)}/mes",
            "monthly_premium_clp_label": f"${_fmt_clp(current_premium_clp)}",
            "rc_label": _comp_summary(current.get("rc")),
            "rc_emergente_label": _comp_summary(current.get("rc_emergente")),
            "rc_moral_label": _comp_summary(current.get("rc_moral")),
            "rc_lucro_cesante_label": _comp_summary(current.get("rc_lucro_cesante")),
            "rc_exceso_label": _comp_summary(current.get("rc_exceso")),
            "auto_replacement_label": _comp_summary(current.get("auto_replacement")),
            "copago_reemplazo_label": _comp_summary(current.get("copago_reemplazo")),
            "workshop_label": _comp_summary(current.get("workshop")),
            "reposicion_a_nuevo_label": _comp_summary(current.get("reposicion_a_nuevo")),
            "perdida_total_label": _comp_summary(current.get("perdida_total")),
            "assistance_label": _comp_summary(current.get("assistance")),
            "asiento_pasajeros_label": _comp_summary(current.get("asiento_pasajeros")),
            "defensa_penal_label": _comp_summary(current.get("defensa_penal")),
        }
    else:
        render_current = None
        current_ded = ""

    base_ded = context.get("base_deductible_uf")
    if not base_ded:
        base_ded = current_ded
    if not base_ded:
        # Fallback to recommended or first offer's comparison deductible
        recommended_id = recommendation.get("recommended_offer_id", "")
        for offer in offers_raw:
            if offer.get("offer_id") == recommended_id or offer.get("recommended"):
                base_ded = _dv(offer.get("comparison_deductible_uf"))
                break
        if not base_ded and offers_raw:
            base_ded = _dv(offers_raw[0].get("comparison_deductible_uf"))

    headline = _dv(recommendation.get("headline_insight"))
    recommended_id = recommendation.get("recommended_offer_id", "")

    render_context = {
        "deductible_explainer_title": "¿Qué es el deducible?",
        "deductible_explainer_body": (
            "Es el monto que pagas de tu bolsillo en cada siniestro. "
            "Un deducible más bajo reduce tu gasto ante un choque o daño, "
            "pero suele significar una prima mensual algo más alta."
        ),
        "methodology_note": (
            (
                f"Los precios se muestran con deducible {_fmt_uf(base_ded)} UF para comparar en igualdad de condiciones. "
                f"Las cotizaciones reflejan la modalidad de **11 cuotas** cuando el PDF la declara."
            )
            if base_ded
            else (
                "Los precios se muestran según deducible seleccionado. "
                "Las cotizaciones reflejan la modalidad de **11 cuotas** cuando el PDF la declara."
            )
        ),
        "headline_insight": headline,
        "base_deductible_uf": base_ded,
    }

    # Comparativo estándar: modalidad de referencia 11 cuotas (extracción debe buscarla en el PDF)
    cuotas_base_val = "11 cuotas"

    render_offers = []
    for offer_idx, offer in enumerate(offers_raw):
        position = offer.get("position", offer_idx + 1)
        tier_matches_selection = (
            _dv(offer.get("commercial_tier", {}).get("value") if isinstance(offer.get("commercial_tier"), dict) else offer.get("commercial_tier")).lower()
            == selected_tier.replace("_option", "").lower()
        )
        is_rec = (
            offer.get("offer_id") == recommended_id
            or (not recommended_id and tier_matches_selection)
        )

        ded_options = []
        for opt in offer.get("deductible_options", []):
            ded_uf = opt.get("deductible_uf", "?")
            prem_uf = opt.get("monthly_premium_uf", "?")
            prem_clp = opt.get("monthly_premium_clp")
            if prem_clp is None and uf_val and prem_uf != "?":
                try:
                    prem_clp = int(round(float(str(prem_uf).replace(",", ".")) * uf_val))
                except (ValueError, TypeError):
                    prem_clp = None
            ded_options.append({
                "deductible_label": f"{_fmt_uf(ded_uf)} UF",
                "premium_label": f"UF {_fmt_uf(prem_uf)}/mes",
                "premium_clp_label": f"~${_fmt_clp(prem_clp)}" if prem_clp else "",
                "is_same_as_current": opt.get("is_same_as_current", False),
                "is_proposed": opt.get("is_proposed", False),
            })

        extra_highlights = [_dv(eh) for eh in offer.get("extra_highlights", []) if _dv(eh)]

        raw_tier = _dv(offer.get("commercial_tier"))
        if offer_tier_overrides and position in offer_tier_overrides:
            raw_tier = offer_tier_overrides[position]
        category, badge_label = _map_tier_to_category_and_badge(raw_tier)

        assistance_display = _coverage_display(offer.get("assistance"))
        assistance_display["value"] = ASSISTANCE_LABEL_BY_CATEGORY.get(
            category, assistance_display["value"]
        )

        installments_val = _dv(offer.get("installments"))
        payment_method_val = _dv(offer.get("payment_method"))
        ded_payment_label = _build_deductible_payment_label(
            _dv(offer.get("comparison_deductible_uf")),
            installments_val,
            payment_method_val,
        )

        savings_raw = _dv(offer.get("monthly_savings_vs_current_clp"))
        savings_label = _build_savings_label(savings_raw) if has_current else ""

        render_offers.append({
            "position": position,
            "recommended": is_rec,
            "recommended_badge_label": "RECOMENDADA" if is_rec else "",
            "tier_label": badge_label,
            "category": category,
            "column_theme": COLUMN_THEME_BY_POSITION.get(position, "azul"),
            "badge_label": badge_label,
            "insurer": _dv(offer.get('insurer')),
            "product_name": _dv(offer.get('product_name')),
            "product_title": f"{_dv(offer.get('insurer'))} {_dv(offer.get('product_name'))}".strip(),
            "monthly_premium_uf_label": f"UF {_fmt_uf(_dv(offer.get('monthly_premium_uf')))}/mes",
            "monthly_premium_clp_label": f"~${_fmt_clp(_dv(offer.get('monthly_premium_clp')))} mensual",
            "deductible_payment_label": ded_payment_label,
            "savings_label": savings_label,
            "rc": _coverage_display(offer.get("rc")),
            "rc_emergente": _coverage_display(offer.get("rc_emergente")),
            "rc_moral": _coverage_display(offer.get("rc_moral")),
            "rc_lucro_cesante": _coverage_display(offer.get("rc_lucro_cesante")),
            "rc_exceso": _coverage_display(offer.get("rc_exceso")),
            "auto_replacement": _coverage_display(offer.get("auto_replacement")),
            "copago_reemplazo": _coverage_display(offer.get("copago_reemplazo")),
            "workshop": _coverage_display(offer.get("workshop")),
            "reposicion_a_nuevo": _coverage_display(offer.get("reposicion_a_nuevo")),
            "perdida_total": _coverage_display(offer.get("perdida_total")),
            "assistance": assistance_display,
            "asiento_pasajeros": _coverage_display(offer.get("asiento_pasajeros")),
            "defensa_penal": _coverage_display(offer.get("defensa_penal")),
            "deductible_options_title": "OPCIONES DE DEDUCIBLE" if ded_options else "",
            "deductible_options": ded_options,
            "extra_highlights_title": "",
            "extra_highlights": [],
            "summary_note": _dv(offer.get("editorial_summary", "")),
            **_format_editorial_summary(_dv(offer.get("editorial_summary", ""))),
        })

    render_offers.sort(key=lambda o: o["position"])

    return {
        "meta": {
            "date_label": uf_date or "2026",
            "uf_value_used": uf_val,
            "uf_value_used_formatted": _fmt_clp(uf_val) if uf_val else "0",
            "uf_0_clp_formatted": _fmt_clp(0),
            "uf_3_clp_formatted": _fmt_clp(uf_val * 3) if uf_val else "0",
            "uf_5_clp_formatted": _fmt_clp(uf_val * 5) if uf_val else "0",
            "uf_10_clp_formatted": _fmt_clp(uf_val * 10) if uf_val else "0",
            "uf_reference_date": uf_date,
            "cuotas_base_label": cuotas_base_val,
        },
        "branding": {
            "broker_name": broker_name,
            "broker_website": broker_website,
        },
        "insured": render_insured,
        "current_policy": render_current,
        "comparison_context": render_context,
        "offers": render_offers,
        "footer": {
            "valuation_note": f"Valores referenciales calculados con UF ${_fmt_clp(uf_val)} al {uf_date}" if uf_val else f"Valores referenciales calculados al {uf_date}",
            "validity_note": "Cotizaciones sujetas a inspección y aprobación de cada compañía",
            "broker_signature": f"{broker_name} · {broker_website}",
        },
    }


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _dv(field) -> str:
    """Extract display value from a derivedField or plain value."""
    if field is None:
        return ""
    if isinstance(field, dict):
        val = field.get("value")
        if val is None:
            return ""
        return str(val)
    return str(field)


def _normalize_coverage_value(value: str) -> tuple[str, bool]:
    """Normalize coverage text; pure LUC placeholder without amount becomes red '--'."""
    if not value or value == "-":
        return value or "-", False
    v = value.strip()
    v_lower = v.lower()
    if "incluido en luc" in v_lower or v_lower == "luc" or v_lower == "--":
        if any(c.isdigit() for c in v):
            return v, False
        return "--", True
    return v, False


def _comp_summary(comp_result) -> str:
    """Get summary text from a comparisonResult."""
    if not isinstance(comp_result, dict):
        return "-"
    summary = comp_result.get("summary")
    if isinstance(summary, dict):
        raw = str(summary.get("value", "-"))
    else:
        raw = str(summary) if summary else "-"
    value, _ = _normalize_coverage_value(raw)
    return value


def _coverage_display(comp_result) -> dict:
    """Build coverage display dict for template."""
    if not isinstance(comp_result, dict):
        return {"value": "-", "comparison_label": "", "is_luc_empty": False}
    summary = comp_result.get("summary")
    value = _dv(summary) if isinstance(summary, dict) else (str(summary) if summary else "-")
    label = comp_result.get("label", "")
    value, is_luc = _normalize_coverage_value(value)
    return {"value": value, "comparison_label": label, "is_luc_empty": is_luc}


def _nowrap_money_in_text(text: str) -> str:
    """Wrap CLP amounts so WeasyPrint does not break $5.000 across lines."""
    if not text:
        return ""

    def repl(match: re.Match) -> str:
        return f'<span class="money-nowrap">{match.group(0)}</span>'

    return re.sub(r"(?:~)?\$[\d]{1,3}(?:\.[\d]{3})+", repl, text)


def _format_editorial_summary(text: str) -> dict:
    """Split editorial text without breaking thousands separators in money."""
    text = (text or "").strip()
    if not text:
        return {"summary_lead": "", "summary_rest": ""}

    match = re.search(r"(?<!\d)\.\s+", text)
    if match:
        lead = text[: match.start() + 1].strip()
        rest = text[match.end() :].strip()
    else:
        lead, rest = text, ""

    return {
        "summary_lead": _nowrap_money_in_text(lead),
        "summary_rest": _nowrap_money_in_text(rest),
    }


def _resolve_tier_label(raw: str) -> str:
    """Map role-based or free-text tier to a clean commercial label."""
    if not raw:
        return ""
    key = raw.strip().lower().replace(" ", "_")
    if key in TIER_DISPLAY_MAP:
        return TIER_DISPLAY_MAP[key]
    if raw.isupper() and len(raw) < 20:
        return raw
    return raw.upper()


def _fmt_uf(val) -> str:
    """Format a UF value: Chilean style (comma decimal), strip trailing .0."""
    if val is None or val == "":
        return "0"
    try:
        num = float(str(val).replace(",", "."))
    except (ValueError, TypeError):
        return str(val)
    if num == int(num):
        return str(int(num))
    formatted = f"{num:.2f}"
    return formatted.replace(".", ",")


def _fmt_clp(val) -> str:
    """Format a CLP integer with dot thousands separator.

    Handles both raw numbers (39947.6) and pre-formatted strings ($39.947).
    """
    if not val and val != 0:
        return "0"
    try:
        s = str(val).strip().replace("$", "").strip()
        if isinstance(val, (int, float)):
            num = int(round(val))
        elif re.match(r"^-?\d{1,3}(\.\d{3})+$", s):
            num = int(s.replace(".", ""))
        else:
            num = int(round(float(s.replace(",", "."))))
        if num < 0:
            return f"-{abs(num):,}".replace(",", ".")
        return f"{num:,}".replace(",", ".")
    except (ValueError, TypeError):
        return str(val)


def _build_deductible_payment_label(ded_uf: str, installments: str, payment_method: str) -> str:
    """Build 'Deducible X UF · N cuotas METHOD' without duplication."""
    parts = [f"Deducible {_fmt_uf(ded_uf)} UF"]

    inst_clean = installments.strip() if installments else ""
    method_clean = payment_method.strip() if payment_method else ""

    has_cuotas_in_inst = "cuota" in inst_clean.lower()
    has_method_in_inst = any(m in inst_clean.upper() for m in ("PAT", "PAC", "TARJ"))

    if has_cuotas_in_inst:
        parts.append(inst_clean)
    elif inst_clean:
        try:
            n = int(float(inst_clean))
            parts.append(f"{n} cuotas")
        except (ValueError, TypeError):
            parts.append(f"{inst_clean} cuotas")

    if method_clean and not has_method_in_inst:
        method_upper = method_clean.upper()
        if method_upper not in ("", "N/A", "NO ESPECIFICADO", "DESCONOCIDO"):
            parts.append(method_upper)

    return " · ".join(parts)


def _build_savings_label(savings_raw: str) -> str:
    """Build savings label, handling negative values as 'Sobrecosto'."""
    if not savings_raw:
        return ""
    try:
        cleaned = str(savings_raw).replace("$", "").replace(".", "").replace(",", ".")
        num = int(round(float(cleaned)))
    except (ValueError, TypeError):
        return f"Ahorro ~${savings_raw}/mes vs. hoy"

    if num > 0:
        return f"Ahorro ~${_fmt_clp(num)}/mes vs. hoy"
    elif num < 0:
        return f"Sobrecosto ~${_fmt_clp(abs(num))}/mes vs. hoy"
    else:
        return "Mismo precio que hoy"
