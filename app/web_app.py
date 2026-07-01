from __future__ import annotations

import base64
import hashlib
import hmac
import os
import json
import re
import shutil
import uuid
from datetime import date
from pathlib import Path

if "DYLD_LIBRARY_PATH" not in os.environ:
    os.environ["DYLD_LIBRARY_PATH"] = "/opt/homebrew/lib"

import streamlit as st

from src.config import (
    DEFAULT_PRIMARY_MODEL,
    OPENROUTER_API_KEY,
    RUNS_DIR,
)
from src.metrics import SessionMetrics
from src.openrouter import OpenRouterClient
from src.pdf_generator import generate_summary_pdf
from src.pipeline import _parse_json_response
from src.run_store import save_run
from src.uf_reference import UFReferenceError, resolve_reference_uf
from src.number_utils import parse_chilean_number
from src.prompts import build_analysis_prompt

ROLE_DISPLAY = {
    "current_policy": "Póliza actual",
    "initial_option": "Básico",
    "middle_option": "Equilibrado",
    "pro_option": "Pro",
}
ROLE_KEYS = list(ROLE_DISPLAY.keys())
ROLE_LABELS = list(ROLE_DISPLAY.values())

CASE_MODE_CURRENT = "current_policy_plus_quotes"
CASE_MODE_QUOTES_ONLY_4 = "quotes_only_4"
CASE_MODE_LABELS = {
    CASE_MODE_CURRENT: "Póliza actual + cotizaciones",
    CASE_MODE_QUOTES_ONLY_4: "4 cotizaciones sin póliza actual",
}
LEGACY_CASE_MODE_LABELS = {
    "Póliza actual + cotizaciones": CASE_MODE_CURRENT,
    "4 cotizaciones sin póliza actual": CASE_MODE_QUOTES_ONLY_4,
}
QUOTE_ROLE_KEYS = [key for key in ROLE_KEYS if key != "current_policy"]
QUOTE_ROLE_LABELS = [ROLE_DISPLAY[key] for key in QUOTE_ROLE_KEYS]
REFCAR_LOGO_PATH = Path(__file__).resolve().parent / "static" / "refcar-logo.jpg"
LOGIN_USER_ENV = "REFCAR_LOGIN_USER"
LOGIN_PASSWORD_ENV = "REFCAR_LOGIN_PASSWORD"
DEFAULT_LOGIN_USER = "felipe_carmona"
AUTH_QUERY_PARAM = "refcar_auth"
DRAFT_QUERY_PARAM = "refcar_draft"
DRAFTS_DIR = RUNS_DIR / "drafts"


def _apply_refcar_theme() -> None:
    st.markdown(
        """
        <style>
        :root {
            --refcar-navy: #071462;
            --refcar-navy-soft: #14226F;
            --refcar-cyan: #21B7E8;
            --refcar-green: #91F21B;
            --refcar-bg: #F4F8FC;
            --refcar-surface: #FFFFFF;
            --refcar-surface-soft: #F8FBFE;
            --refcar-border: #D8E3EE;
            --refcar-text: #172033;
            --refcar-muted: #637083;
            --refcar-shadow: 0 18px 50px rgba(7, 20, 98, 0.10);
        }
        .stApp {
            background:
                radial-gradient(circle at 12% 8%, rgba(33, 183, 232, 0.18), transparent 30%),
                radial-gradient(circle at 88% 10%, rgba(145, 242, 27, 0.16), transparent 28%),
                linear-gradient(135deg, #FFFFFF 0%, #F4F9FD 48%, #EEF7FC 100%);
            color: var(--refcar-text);
        }
        [data-testid="stHeader"] {
            background: rgba(244, 248, 252, 0.78);
            backdrop-filter: blur(14px);
        }
        [data-testid="stSidebar"] {
            background:
                linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(238, 247, 252, 0.96));
            border-right: 1px solid var(--refcar-border);
            box-shadow: 8px 0 30px rgba(7, 20, 98, 0.06);
        }
        .block-container {
            padding-top: 2.4rem;
            max-width: 1240px;
        }
        h1, h2, h3, h4, h5, h6,
        [data-testid="stMarkdownContainer"] h1,
        [data-testid="stMarkdownContainer"] h2,
        [data-testid="stMarkdownContainer"] h3 {
            color: var(--refcar-navy);
            letter-spacing: -0.025em;
        }
        p, label, span, div[data-testid="stMarkdownContainer"] {
            color: var(--refcar-text);
        }
        [data-testid="stCaptionContainer"],
        [data-testid="stMarkdownContainer"] p,
        small {
            color: var(--refcar-muted);
        }
        [data-testid="stSidebar"] h1,
        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3,
        [data-testid="stSidebar"] p,
        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] span,
        [data-testid="stSidebar"] div[data-testid="stMarkdownContainer"] {
            color: var(--refcar-text);
        }
        [data-testid="stSidebar"] [data-testid="stCaptionContainer"],
        [data-testid="stSidebar"] small {
            color: var(--refcar-muted);
        }
        div[data-testid="stFileUploaderDropzone"],
        div[data-testid="stExpander"],
        div[data-testid="stDataFrame"],
        div[data-testid="stAlert"],
        div[data-testid="stVerticalBlockBorderWrapper"] {
            border-color: var(--refcar-border) !important;
            background: rgba(255, 255, 255, 0.94) !important;
            box-shadow: 0 10px 28px rgba(7, 20, 98, 0.06);
        }
        div[data-testid="stExpander"] {
            border-radius: 18px;
            overflow: hidden;
        }
        div[data-testid="stExpander"] details,
        div[data-testid="stExpander"] details > div {
            background: var(--refcar-surface) !important;
            color: var(--refcar-text) !important;
        }
        div[data-testid="stExpander"] summary {
            background:
                linear-gradient(90deg, rgba(33, 183, 232, 0.10), rgba(145, 242, 27, 0.10)) !important;
            border-bottom: 1px solid var(--refcar-border) !important;
            color: var(--refcar-navy) !important;
        }
        div[data-testid="stExpander"] summary:hover {
            background:
                linear-gradient(90deg, rgba(33, 183, 232, 0.16), rgba(145, 242, 27, 0.14)) !important;
        }
        div[data-testid="stExpander"] summary svg {
            color: var(--refcar-navy) !important;
            fill: var(--refcar-navy) !important;
        }
        div[data-testid="stFileUploaderDropzone"] {
            border-radius: 20px;
            background:
                linear-gradient(135deg, rgba(255,255,255,0.98), rgba(238,247,252,0.94)) !important;
            border: 1px dashed rgba(33, 183, 232, 0.42) !important;
            color: var(--refcar-text) !important;
        }
        div[data-testid="stFileUploaderDropzone"] * {
            color: var(--refcar-text) !important;
        }
        div[data-testid="stFileUploaderDropzone"] button {
            background: var(--refcar-surface) !important;
            color: var(--refcar-navy) !important;
            border: 1px solid var(--refcar-border) !important;
            box-shadow: 0 8px 18px rgba(7, 20, 98, 0.08) !important;
        }
        div[data-testid="stFileUploaderDropzone"] small {
            color: var(--refcar-muted) !important;
        }
        div[data-testid="stFileUploaderDropzone"] svg {
            color: var(--refcar-cyan) !important;
            fill: var(--refcar-cyan) !important;
        }
        div[data-baseweb="select"] > div,
        div[data-baseweb="input"] > div,
        div[data-baseweb="textarea"] textarea {
            background: var(--refcar-surface) !important;
            border: 1.5px solid rgba(7, 20, 98, 0.26) !important;
            color: var(--refcar-text) !important;
            border-radius: 13px !important;
            box-shadow: none !important;
        }
        div[data-baseweb="input"] input,
        div[data-baseweb="select"] input,
        div[data-baseweb="textarea"] textarea,
        input[type="text"],
        input[type="password"],
        input[type="number"] {
            border: 0 !important;
            outline: 0 !important;
            box-shadow: none !important;
            background: transparent !important;
        }
        div[data-baseweb="select"] input {
            caret-color: transparent !important;
            color: transparent !important;
            min-width: 0 !important;
            width: 0 !important;
            padding: 0 !important;
            margin: 0 !important;
        }
        div[data-baseweb="input"] > div:hover,
        div[data-baseweb="select"] > div:hover,
        div[data-baseweb="textarea"] textarea:hover,
        div[data-baseweb="input"] > div:focus-within,
        div[data-baseweb="select"] > div:focus-within,
        div[data-baseweb="textarea"] textarea:focus {
            border-color: rgba(7, 20, 98, 0.42) !important;
            box-shadow: 0 0 0 2px rgba(33, 183, 232, 0.10) !important;
            outline: none !important;
        }
        div[data-baseweb="input"] input,
        div[data-baseweb="textarea"] textarea,
        div[data-baseweb="select"] input {
            color: var(--refcar-text) !important;
            font-weight: 650 !important;
        }
        [data-testid="stNumberInput"] button,
        [data-testid="stNumberInput"] [role="button"] {
            background: #EAF7FE !important;
            color: var(--refcar-navy) !important;
            border: 1.5px solid rgba(7, 20, 98, 0.18) !important;
            box-shadow: none !important;
        }
        [data-testid="stNumberInput"] button svg,
        [data-testid="stNumberInput"] [role="button"] svg {
            color: var(--refcar-navy) !important;
            fill: var(--refcar-navy) !important;
        }
        input::placeholder,
        textarea::placeholder {
            color: #8A96A8 !important;
        }
        div[data-baseweb="select"] svg,
        div[data-baseweb="checkbox"] svg,
        [data-testid="stRadio"] svg,
        [data-testid="stCheckbox"] svg {
            color: var(--refcar-navy) !important;
            fill: var(--refcar-navy) !important;
        }
        .stButton button,
        .stDownloadButton button,
        button[kind="primary"],
        button[data-testid="baseButton-primary"] {
            border-radius: 999px !important;
            border: 0 !important;
            background: linear-gradient(90deg, #21B7E8, #64D86C) !important;
            color: var(--refcar-navy) !important;
            font-weight: 850 !important;
            box-shadow: 0 10px 22px rgba(7, 20, 98, 0.14);
        }
        .stButton button:hover,
        .stDownloadButton button:hover,
        button[kind="primary"]:hover,
        button[data-testid="baseButton-primary"]:hover {
            transform: translateY(-1px);
            box-shadow: 0 14px 26px rgba(7, 20, 98, 0.18);
        }
        button[data-testid="baseButton-secondary"],
        .stButton button[kind="secondary"] {
            background: var(--refcar-surface) !important;
            color: var(--refcar-navy) !important;
            border: 1px solid var(--refcar-border) !important;
            box-shadow: 0 8px 18px rgba(7, 20, 98, 0.08);
        }
        [data-testid="stRadio"] label,
        [data-testid="stCheckbox"] label {
            color: var(--refcar-text) !important;
        }
        label[data-baseweb="radio"],
        label[data-baseweb="checkbox"] {
            color: var(--refcar-text) !important;
        }
        [data-testid="stRadio"] [role="radio"],
        [data-testid="stCheckbox"] [role="checkbox"],
        [data-testid="stRadio"] input[type="radio"],
        [data-testid="stCheckbox"] input[type="checkbox"],
        input[type="radio"],
        input[type="checkbox"] {
            accent-color: var(--refcar-navy) !important;
            border-color: var(--refcar-navy) !important;
            color: var(--refcar-navy) !important;
        }
        [data-testid="stRadio"] div[role="radiogroup"] > label > div:first-child,
        [data-testid="stCheckbox"] label > div:first-child,
        [data-testid="stRadio"] label > div:first-child,
        label[data-baseweb="radio"] > div:first-child,
        label[data-baseweb="checkbox"] > span:first-child {
            background: var(--refcar-surface) !important;
            border: 2px solid rgba(7, 20, 98, 0.55) !important;
            box-shadow: inset 0 0 0 3px var(--refcar-surface) !important;
        }
        [data-testid="stRadio"] div[role="radiogroup"] > label[data-checked="true"] > div:first-child,
        [data-testid="stCheckbox"] label[data-checked="true"] > div:first-child,
        [data-testid="stRadio"] label[data-checked="true"] > div:first-child,
        label[data-baseweb="radio"]:has(input:checked) > div:first-child,
        label[data-baseweb="checkbox"]:has(input:checked) > span:first-child {
            background: var(--refcar-navy) !important;
            border-color: var(--refcar-navy) !important;
            box-shadow: inset 0 0 0 4px var(--refcar-surface) !important;
        }
        label[data-baseweb="radio"]:has(input:checked) > div:first-child > div,
        label[data-baseweb="checkbox"]:has(input:checked) > span:first-child > div {
            background: var(--refcar-navy) !important;
            border-color: var(--refcar-navy) !important;
        }
        [data-testid="stRadio"] svg,
        [data-testid="stCheckbox"] svg {
            color: var(--refcar-navy) !important;
            fill: var(--refcar-navy) !important;
        }
        [data-testid="stMetricValue"],
        code {
            color: var(--refcar-navy) !important;
            background: rgba(33, 183, 232, 0.10) !important;
            border-radius: 8px;
        }
        div[data-testid="stDataFrame"],
        div[data-testid="stTable"],
        div[data-testid="stTable"] table {
            background: var(--refcar-surface) !important;
            color: var(--refcar-text) !important;
        }
        hr {
            border-color: var(--refcar-border);
        }
        .refcar-login-shell {
            max-width: 760px;
            margin: 2.2rem auto 1.4rem;
        }
        .refcar-login-card {
            padding: 42px;
            border: 1px solid rgba(7, 20, 98, 0.10);
            border-radius: 30px;
            background:
                linear-gradient(145deg, rgba(255,255,255,0.98), rgba(238,247,252,0.88));
            box-shadow: var(--refcar-shadow);
            backdrop-filter: blur(18px);
            text-align: center;
        }
        .refcar-login-logo {
            display: block;
            width: 150px;
            height: 150px;
            margin: 0 auto 22px;
            border-radius: 999px;
            box-shadow: 0 18px 45px rgba(33, 183, 232, 0.22);
        }
        .refcar-login-title {
            margin: 0;
            color: var(--refcar-navy);
            font-size: 2.35rem;
            font-weight: 850;
            letter-spacing: 0;
        }
        .refcar-login-subtitle {
            margin: 12px auto 0;
            max-width: 640px;
            color: var(--refcar-muted);
            font-size: 1.03rem;
            line-height: 1.55;
            text-align: center;
        }
        .refcar-login-chip {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 18px;
            padding: 7px 13px;
            border: 1px solid rgba(145, 242, 27, 0.40);
            border-radius: 999px;
            color: var(--refcar-navy);
            background: linear-gradient(90deg, rgba(33, 183, 232, 0.14), rgba(145, 242, 27, 0.20));
            font-size: 0.84rem;
            font-weight: 700;
            letter-spacing: 0.02em;
            text-transform: uppercase;
        }
        .refcar-login-form {
            max-width: 440px;
            margin: 0 auto;
        }
        div[data-testid="stForm"] {
            border: 0;
            padding: 0;
            background: transparent;
            max-width: 560px;
            margin: 0 auto;
        }
        div[data-testid="stForm"] input {
            border-radius: 14px;
        }
        div[data-testid="stForm"] .stFormSubmitButton button {
            border-radius: 999px;
            min-height: 48px;
            background: linear-gradient(90deg, #21B7E8, #91F21B);
            color: #071462;
            font-weight: 850;
            border: 0;
        }
        div[data-testid="stForm"] button[aria-label*="password"],
        div[data-testid="stForm"] button[title*="password"],
        div[data-testid="stForm"] button[kind="icon"] {
            min-height: 0;
            width: 42px;
            height: 42px;
            padding: 0;
            border: 0;
            border-radius: 10px;
            background: transparent;
            color: var(--refcar-navy);
            box-shadow: none;
        }
        div[data-testid="stForm"] button[aria-label*="password"]:hover,
        div[data-testid="stForm"] button[title*="password"]:hover,
        div[data-testid="stForm"] button[kind="icon"]:hover {
            background: rgba(33, 183, 232, 0.10);
            color: var(--refcar-navy);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_login() -> None:
    expected_user = os.getenv(LOGIN_USER_ENV, DEFAULT_LOGIN_USER).strip()
    expected_password = os.getenv(LOGIN_PASSWORD_ENV, "").strip()
    logo_html = ""
    if REFCAR_LOGO_PATH.is_file():
        logo_b64 = base64.b64encode(REFCAR_LOGO_PATH.read_bytes()).decode("ascii")
        logo_html = f'<img class="refcar-login-logo" src="data:image/jpeg;base64,{logo_b64}" alt="Refcar">'

    st.markdown(
        f"""
        <section class="refcar-login-shell">
            <div class="refcar-login-card">
                <div class="refcar-login-chip">Acceso privado Refcar</div>
                {logo_html}
                <h1 class="refcar-login-title">Herramienta Comparativa Refcar</h1>
                <p class="refcar-login-subtitle">
                    Ingresa con tus credenciales para generar comparativos de seguros y descargar propuestas en PDF.
                </p>
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )

    if not expected_password:
        st.error(f"Falta configurar `{LOGIN_PASSWORD_ENV}` en Railway.")
        st.stop()

    with st.form("refcar_login_form"):
        username = st.text_input("Usuario", placeholder="usuario")
        password = st.text_input("Clave", type="password", placeholder="clave")
        submitted = st.form_submit_button("Entrar a Refcar", use_container_width=True)

    if submitted:
        user_ok = hmac.compare_digest(username.strip(), expected_user)
        password_ok = hmac.compare_digest(password, expected_password)
        if user_ok and password_ok:
            st.session_state.refcar_authenticated = True
            st.query_params[AUTH_QUERY_PARAM] = _build_auth_token(expected_user, expected_password)
            st.rerun()
        else:
            st.error("Usuario o clave incorrectos.")

    st.stop()


def _build_auth_token(username: str, password: str) -> str:
    secret = password.encode("utf-8")
    message = f"refcar-login:{username}".encode("utf-8")
    return hmac.new(secret, message, hashlib.sha256).hexdigest()


def _get_query_param_value(name: str) -> str:
    raw_token = st.query_params.get(name, "")
    if isinstance(raw_token, list):
        return str(raw_token[0] if raw_token else "")
    return str(raw_token or "")


def _get_query_auth_token() -> str:
    return _get_query_param_value(AUTH_QUERY_PARAM)


def _query_auth_is_valid() -> bool:
    expected_user = os.getenv(LOGIN_USER_ENV, DEFAULT_LOGIN_USER).strip()
    expected_password = os.getenv(LOGIN_PASSWORD_ENV, "").strip()
    if not expected_password:
        return False
    expected_token = _build_auth_token(expected_user, expected_password)
    return hmac.compare_digest(_get_query_auth_token(), expected_token)


def _clear_query_auth_token() -> None:
    try:
        del st.query_params[AUTH_QUERY_PARAM]
    except KeyError:
        pass


def _clear_query_draft_token() -> None:
    try:
        del st.query_params[DRAFT_QUERY_PARAM]
    except KeyError:
        pass


def _require_login() -> None:
    if "refcar_authenticated" not in st.session_state:
        st.session_state.refcar_authenticated = _query_auth_is_valid()
    if not st.session_state.refcar_authenticated:
        _render_login()

# ------------------------------------------------------------------
# Getters and Setters for analysis schema elements
# ------------------------------------------------------------------
def _get_val(field) -> str:
    if isinstance(field, dict):
        v = field.get("value")
        return str(v) if v is not None else ""
    return str(field) if field is not None else ""


def _normalize_case_mode(raw_mode) -> str:
    if raw_mode in CASE_MODE_LABELS:
        return raw_mode
    if raw_mode in LEGACY_CASE_MODE_LABELS:
        return LEGACY_CASE_MODE_LABELS[raw_mode]
    return CASE_MODE_CURRENT

def _default_derived_field(value=""):
    return {"value": value, "confidence": 1.0, "method": "manual"}


def _ensure_derived_field(container: dict, key: str, default=""):
    field = container.get(key)
    if not isinstance(field, dict):
        container[key] = _default_derived_field(default)
    elif "value" not in field:
        field["value"] = default
        field.setdefault("confidence", 1.0)
        field.setdefault("method", "manual")
    return container[key]


def _ensure_comparison_result(container: dict, key: str, label: str = "IGUAL"):
    comp = container.get(key)
    if not isinstance(comp, dict):
        comp = {}
        container[key] = comp
    if not isinstance(comp.get("summary"), dict):
        comp["summary"] = _default_derived_field("")
    comp.setdefault("label", label)
    return comp


def _set_val(field_obj, new_value):
    if isinstance(field_obj, dict):
        field_obj["value"] = new_value
        field_obj["method"] = "manual"
        field_obj["confidence"] = 1.0

def _get_summary_val(comp_result) -> str:
    if isinstance(comp_result, dict):
        return _get_val(comp_result.get("summary", {}))
    return ""

def _set_summary_val(comp_result, new_value):
    if isinstance(comp_result, dict):
        summary = comp_result.setdefault("summary", {})
        _set_val(summary, new_value)

def _get_label_val(comp_result) -> str:
    if isinstance(comp_result, dict):
        return comp_result.get("label", "IGUAL")
    return "IGUAL"

def _set_label_val(comp_result, new_label):
    if isinstance(comp_result, dict):
        comp_result["label"] = new_label


_COVERAGE_KEYS = (
    "rc",
    "rc_emergente",
    "rc_moral",
    "rc_lucro_cesante",
    "rc_exceso",
    "auto_replacement",
    "copago_reemplazo",
    "workshop",
    "reposicion_a_nuevo",
    "perdida_total",
    "assistance",
    "asiento_pasajeros",
    "defensa_penal",
)


def _prepare_analysis_for_editor(analysis: dict) -> bool:
    """Ensure nested dicts exist for the editor. Returns False if analysis failed."""
    if not isinstance(analysis, dict) or analysis.get("error"):
        return False
    analysis.setdefault("context", {})
    insured = analysis.setdefault("insured", {})
    for key in (
        "name",
        "vehicle_display_name",
        "plate",
        "vehicle_make",
        "vehicle_model",
        "vehicle_year",
        "usage",
    ):
        _ensure_derived_field(insured, key)

    recommendation = analysis.setdefault("recommendation", {})
    for key in ("headline_insight", "reason_summary"):
        _ensure_derived_field(recommendation, key)

    analysis.setdefault("footer", {
        "broker_name": "Convision Corredores de Seguros SpA",
        "broker_website": "www.convision.cl",
    })

    current = analysis.get("current_policy")
    if isinstance(current, dict):
        for key in (
            "insurer",
            "product_name",
            "deductible_uf",
            "monthly_premium_uf",
            "monthly_premium_clp",
        ):
            _ensure_derived_field(current, key)
        for key in _COVERAGE_KEYS:
            _ensure_comparison_result(current, key)

    if analysis.get("offers") is None:
        analysis["offers"] = []

    for offer in analysis["offers"]:
        if not isinstance(offer, dict):
            continue
        for key in (
            "insurer",
            "product_name",
            "commercial_tier",
            "comparison_deductible_uf",
            "monthly_premium_uf",
            "monthly_premium_clp",
            "payment_method",
            "installments",
            "monthly_savings_vs_current_clp",
            "editorial_summary",
        ):
            _ensure_derived_field(offer, key)
        for key in _COVERAGE_KEYS:
            _ensure_comparison_result(offer, key)
        if offer.get("deductible_options") is None:
            offer["deductible_options"] = []
        if offer.get("extra_highlights") is None:
            offer["extra_highlights"] = []

    return True


def _is_valid_draft_id(draft_id: str) -> bool:
    return bool(re.fullmatch(r"[a-f0-9]{32}", str(draft_id or "")))


def _draft_dir(draft_id: str) -> Path:
    if not _is_valid_draft_id(draft_id):
        raise ValueError("draft_id inválido")
    return DRAFTS_DIR / draft_id


def _draft_state_path(draft_id: str) -> Path:
    return _draft_dir(draft_id) / "draft_state.json"


def _safe_upload_name(index: int, original_name: str) -> str:
    original = Path(original_name or f"documento_{index + 1}.pdf").name
    stem = Path(original).stem or f"documento_{index + 1}"
    clean_stem = re.sub(r"[^A-Za-z0-9._ -]+", "_", stem).strip(" ._")
    if not clean_stem:
        clean_stem = f"documento_{index + 1}"
    return f"{index + 1:02d}_{clean_stem}.pdf"


def _uploaded_payload(uploaded_files) -> list[dict]:
    payload = []
    for idx, item in enumerate(uploaded_files):
        data = item.getvalue() if hasattr(item, "getvalue") else item.read()
        if hasattr(item, "seek"):
            item.seek(0)
        payload.append(
            {
                "name": item.name,
                "safe_name": _safe_upload_name(idx, item.name),
                "size": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
                "data": bytes(data),
            }
        )
    return payload


def _payload_signature(payload: list[dict]) -> str:
    comparable = [
        {"name": item["name"], "size": item["size"], "sha256": item["sha256"]}
        for item in payload
    ]
    return json.dumps(comparable, ensure_ascii=False, sort_keys=True)


def _ensure_active_draft_id() -> str:
    draft_id = str(st.session_state.get("active_draft_id") or "")
    if not _is_valid_draft_id(draft_id):
        draft_id = _get_query_param_value(DRAFT_QUERY_PARAM)
    if not _is_valid_draft_id(draft_id):
        draft_id = uuid.uuid4().hex
    st.session_state.active_draft_id = draft_id
    st.query_params[DRAFT_QUERY_PARAM] = draft_id
    return draft_id


def _current_pdf_display_names() -> list[str]:
    names = list(st.session_state.get("uploaded_file_display_names") or [])
    paths = [Path(p) for p in st.session_state.get("saved_paths", [])]
    if len(names) == len(paths):
        return names
    return [path.name for path in paths]


def _write_draft_state() -> None:
    draft_id = str(st.session_state.get("active_draft_id") or "")
    if not _is_valid_draft_id(draft_id):
        return
    state_path = _draft_state_path(draft_id)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "draft_id": draft_id,
        "step": st.session_state.get("step", "upload"),
        "saved_paths": [str(Path(p)) for p in st.session_state.get("saved_paths", [])],
        "uploaded_file_display_names": _current_pdf_display_names(),
        "uploaded_file_signature": st.session_state.get("uploaded_file_signature", ""),
        "roles": st.session_state.get("roles", []),
        "case_mode": st.session_state.get("case_mode", CASE_MODE_CURRENT),
        "winner_idx": st.session_state.get("winner_idx"),
        "winner_tier_internal": st.session_state.get("winner_tier_internal", ""),
        "winner_quote_position": st.session_state.get("winner_quote_position"),
        "offer_tier_overrides": st.session_state.get("offer_tier_overrides", {}),
        "resolved_extractions": st.session_state.get("resolved_extractions", []),
        "analysis": st.session_state.get("analysis", {}),
        "session_metrics": st.session_state.get("session_metrics", {}),
        "uf_ref": st.session_state.get("uf_ref"),
        "run_status": st.session_state.get("run_status", "idle"),
        "run_error": st.session_state.get("run_error", ""),
        "run_stage": st.session_state.get("run_stage", ""),
    }
    state_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _restore_draft_from_query() -> bool:
    if st.session_state.get("active_draft_id") or st.session_state.get("saved_paths"):
        return False
    draft_id = _get_query_param_value(DRAFT_QUERY_PARAM)
    if not _is_valid_draft_id(draft_id):
        return False
    state_path = _draft_state_path(draft_id)
    if not state_path.is_file():
        return False
    try:
        draft = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False

    saved_paths = [Path(path) for path in draft.get("saved_paths", [])]
    saved_paths = [path for path in saved_paths if path.is_file()]
    if not saved_paths:
        return False

    st.session_state.active_draft_id = draft_id
    st.session_state.saved_paths = saved_paths
    st.session_state.uploaded_file_display_names = (
        draft.get("uploaded_file_display_names") or [path.name for path in saved_paths]
    )
    st.session_state.uploaded_file_signature = draft.get("uploaded_file_signature", "")
    st.session_state.roles = draft.get("roles", [])
    st.session_state.case_mode = _normalize_case_mode(draft.get("case_mode"))
    st.session_state.winner_idx = draft.get("winner_idx")
    st.session_state.winner_tier_internal = draft.get("winner_tier_internal", "")
    st.session_state.winner_quote_position = draft.get("winner_quote_position")
    overrides = draft.get("offer_tier_overrides", {})
    st.session_state.offer_tier_overrides = {
        int(k): v for k, v in overrides.items()
    } if isinstance(overrides, dict) else {}
    st.session_state.resolved_extractions = draft.get("resolved_extractions", [])
    st.session_state.analysis = draft.get("analysis", {})
    st.session_state.session_metrics = draft.get("session_metrics", {})
    uf_ref = draft.get("uf_ref")
    st.session_state.uf_ref = tuple(uf_ref) if isinstance(uf_ref, list) else uf_ref

    restored_status = draft.get("run_status", "idle")
    if restored_status == "running":
        st.session_state.run_status = "failed"
        st.session_state.run_stage = draft.get("run_stage", "corrida")
        st.session_state.run_error = (
            "La sesión se reconectó mientras la corrida estaba en proceso. "
            "Los archivos quedaron recuperados; puedes iniciar de nuevo o reintentar el análisis si hay extracciones."
        )
        if st.session_state.resolved_extractions and not st.session_state.analysis:
            st.session_state.analysis = {
                "error": "run_interrupted",
                "message": st.session_state.run_error,
            }
            st.session_state.step = "editor"
        else:
            st.session_state.step = "upload"
    else:
        st.session_state.run_status = restored_status
        st.session_state.run_error = draft.get("run_error", "")
        st.session_state.run_stage = draft.get("run_stage", "")
        st.session_state.step = draft.get("step", "upload")
    return True


def _persist_uploaded_files(uploaded_files) -> list[Path]:
    payload = _uploaded_payload(uploaded_files)
    signature = _payload_signature(payload)
    existing_paths = [Path(p) for p in st.session_state.get("saved_paths", [])]
    if (
        st.session_state.get("uploaded_file_signature") == signature
        and len(existing_paths) == len(payload)
        and all(path.is_file() for path in existing_paths)
    ):
        return existing_paths

    draft_id = _ensure_active_draft_id()
    draft_dir = _draft_dir(draft_id)
    draft_dir.mkdir(parents=True, exist_ok=True)
    for old_pdf in draft_dir.glob("*.pdf"):
        old_pdf.unlink(missing_ok=True)

    saved_paths = []
    for item in payload:
        out_path = draft_dir / item["safe_name"]
        out_path.write_bytes(item["data"])
        saved_paths.append(out_path)

    st.session_state.saved_paths = saved_paths
    st.session_state.uploaded_file_display_names = [item["name"] for item in payload]
    st.session_state.uploaded_file_signature = signature
    st.session_state.resolved_extractions = []
    st.session_state.analysis = {}
    st.session_state.session_metrics = {}
    _clear_generated_pdf_state()
    if st.session_state.get("run_status") != "running":
        _reset_run_status()
    _write_draft_state()
    return saved_paths


def _clear_active_draft(remove_files: bool = False) -> None:
    draft_id = str(st.session_state.get("active_draft_id") or _get_query_param_value(DRAFT_QUERY_PARAM))
    if remove_files and _is_valid_draft_id(draft_id):
        shutil.rmtree(_draft_dir(draft_id), ignore_errors=True)
    for key in (
        "active_draft_id",
        "uploaded_file_display_names",
        "uploaded_file_signature",
    ):
        st.session_state.pop(key, None)
    _clear_query_draft_token()


def _reset_proposal_state(remove_draft_files: bool = True) -> None:
    st.session_state.step = "upload"
    st.session_state.saved_paths = []
    st.session_state.roles = []
    st.session_state.winner_idx = None
    st.session_state.winner_tier_internal = ""
    st.session_state.winner_quote_position = None
    st.session_state.offer_tier_overrides = {}
    st.session_state.extractions = []
    st.session_state.resolved_extractions = []
    st.session_state.analysis = {}
    st.session_state.session_metrics = {}
    st.session_state.uf_ref = None
    st.session_state._upload_file_count = 0
    st.session_state.upload_widget_nonce = int(st.session_state.get("upload_widget_nonce", 0)) + 1
    _reset_run_status()
    _clear_generated_pdf_state()
    _clear_active_draft(remove_files=remove_draft_files)


def _create_progress_tracker(total_steps: int):
    """Barra de progreso y texto de estado para extracción / análisis."""
    progress_bar = st.progress(0.0)
    status_line = st.empty()

    def on_step(step_name: str, step_number: int, total: int) -> None:
        denom = max(total, 1)
        progress_bar.progress(min(step_number / denom, 1.0))
        status_line.markdown(f"**Paso {step_number}/{total}:** {step_name}")

    def complete(message: str = "Proceso completado.") -> None:
        progress_bar.progress(1.0)
        status_line.success(message)

    # Inicializar en paso 0
    on_step("Preparando...", 0, total_steps)

    return on_step, complete


def _clear_generated_pdf_state() -> None:
    """Discard the previous render when starting a new proposal."""
    for key in ("pdf_bytes", "run_file_name", "run_file_stem"):
        st.session_state.pop(key, None)


def _reset_run_status() -> None:
    st.session_state.run_status = "idle"
    st.session_state.run_error = ""
    st.session_state.run_stage = ""


def _set_run_failed(stage: str, error: Exception | str) -> None:
    st.session_state.run_status = "failed"
    st.session_state.run_stage = stage
    st.session_state.run_error = str(error)


def main():
    st.set_page_config(page_title="Herramienta Seguros Refcar", layout="wide")
    _apply_refcar_theme()
    _require_login()

    st.title("Herramienta de Seguros - Formato Comparativo Refcar")
    st.caption("Evolución de plantillas automatizadas con edición de JSON manual integrada.")

    if not OPENROUTER_API_KEY:
        st.error(
            "No se encontró API key de OpenRouter. "
            "Configura `OPENROUTER_API_KEY` o pega tu key en `MI_OPENROUTER_KEY.txt`."
        )
        st.stop()

    RUNS_DIR.mkdir(parents=True, exist_ok=True)

    # Initialize Session State Machine
    if "step" not in st.session_state:
        st.session_state.step = "upload"
    if "saved_paths" not in st.session_state:
        st.session_state.saved_paths = []
    if "roles" not in st.session_state:
        st.session_state.roles = []
    if "case_mode" not in st.session_state:
        st.session_state.case_mode = CASE_MODE_CURRENT
    st.session_state.case_mode = _normalize_case_mode(st.session_state.case_mode)
    if "upload_winner_file_idx" not in st.session_state:
        st.session_state.upload_winner_file_idx = None
    if "_upload_file_count" not in st.session_state:
        st.session_state._upload_file_count = 0
    if "upload_widget_nonce" not in st.session_state:
        st.session_state.upload_widget_nonce = 0
    if "winner_idx" not in st.session_state:
        st.session_state.winner_idx = None
    if "winner_tier_internal" not in st.session_state:
        st.session_state.winner_tier_internal = ""
    if "winner_quote_position" not in st.session_state:
        st.session_state.winner_quote_position = None
    if "offer_tier_overrides" not in st.session_state:
        st.session_state.offer_tier_overrides = {}
    if "extractions" not in st.session_state:
        st.session_state.extractions = []
    if "resolved_extractions" not in st.session_state:
        st.session_state.resolved_extractions = []
    if "analysis" not in st.session_state:
        st.session_state.analysis = {}
    if "session_metrics" not in st.session_state:
        st.session_state.session_metrics = {}
    if "uf_ref" not in st.session_state:
        st.session_state.uf_ref = None
    if "run_status" not in st.session_state:
        _reset_run_status()
    _restore_draft_from_query()

    # Reset button to start over
    if st.session_state.step != "upload":
        if st.button("← Volver a Cargar PDFs"):
            _reset_proposal_state(remove_draft_files=True)
            st.rerun()

    # ------------------------------------------------------------------
    # STEP 1: UPLOAD AND PARAMETERS
    # ------------------------------------------------------------------
    if st.session_state.step == "upload":
        st.subheader("1) Cargar PDFs de Entrada")
        if st.session_state.get("run_status") == "failed" and st.session_state.get("run_error"):
            stage = st.session_state.get("run_stage") or "corrida"
            st.warning(
                f"La corrida anterior se interrumpió en **{stage}**. "
                f"Detalle: {st.session_state.run_error}"
            )
        uploaded_files = st.file_uploader(
            "Arrastra y suelta los PDFs aquí (3+ cotizaciones con póliza opcional, o exactamente 4 cotizaciones)",
            type=["pdf"],
            accept_multiple_files=True,
            key=f"pdf_uploader_{st.session_state.upload_widget_nonce}",
        )

        with st.sidebar:
            st.markdown("### Refcar")
            st.caption("Sesión iniciada.")
            if st.button("Cerrar sesión", use_container_width=True):
                st.session_state.refcar_authenticated = False
                _clear_query_auth_token()
                _reset_proposal_state(remove_draft_files=True)
                st.rerun()
            st.divider()
            st.header("Configuración")
            case_mode_label = st.radio(
                "Modo de comparación",
                options=list(CASE_MODE_LABELS.values()),
                index=list(CASE_MODE_LABELS.values()).index(
                    CASE_MODE_LABELS[_normalize_case_mode(st.session_state.case_mode)]
                ),
            )
            case_mode = next(
                key for key, label in CASE_MODE_LABELS.items() if label == case_mode_label
            )
            st.session_state.case_mode = case_mode

            model = DEFAULT_PRIMARY_MODEL

            st.divider()
            st.subheader("UF de referencia")
            st.caption("Se consulta automáticamente en mindicador.cl para cada corrida.")
            manual_uf_enabled = st.checkbox(
                "Ingresar UF manualmente",
                value=False,
                help="Actívalo solo si mindicador.cl no responde o necesitas fijar un valor específico.",
            )
            uf_manual_clp = None
            uf_manual_date = None
            if manual_uf_enabled:
                uf_manual_clp = st.number_input(
                    "UF en CLP",
                    min_value=0.0,
                    value=0.0,
                    step=1.0,
                    format="%.2f",
                )
                uf_manual_date = st.date_input(
                    "Fecha de ese valor UF",
                    value=date.today(),
                )

        active_paths: list[Path] = []
        if uploaded_files:
            active_paths = _persist_uploaded_files(uploaded_files)
        else:
            active_paths = [
                Path(path)
                for path in st.session_state.get("saved_paths", [])
                if Path(path).is_file()
            ]

        if not active_paths:
            st.info("Carga PDFs para iniciar la propuesta.")
            st.stop()

        if not uploaded_files:
            st.success(
                "Recuperé los PDFs que ya estaban cargados en esta sesión. "
                "Puedes seguir con ellos o volver a cargar PDFs para iniciar otra propuesta."
            )
            if st.button("Descartar PDFs recuperados y subir otros"):
                _reset_proposal_state(remove_draft_files=True)
                st.rerun()

        file_display_names = _current_pdf_display_names()
        if len(file_display_names) != len(active_paths):
            file_display_names = [path.name for path in active_paths]

        n_files = len(active_paths)
        upload_signature = (
            f"{case_mode}:{n_files}:{st.session_state.get('uploaded_file_signature', '')}"
        )
        if st.session_state.get("_upload_file_count") != upload_signature:
            st.session_state._upload_file_count = upload_signature
            st.session_state.upload_winner_file_idx = None
            st.session_state.pop(f"upload_winner_file_idx_{CASE_MODE_CURRENT}", None)
            st.session_state.pop(f"upload_winner_file_idx_{CASE_MODE_QUOTES_ONLY_4}", None)

        st.subheader("2) Asignar rol y ganador")
        if case_mode == CASE_MODE_QUOTES_ONLY_4:
            st.caption(
                "Modo 4 cotizaciones: todos los PDFs son propuestas nuevas. Asigna la etiqueta comercial "
                "de cada una (Básico, Equilibrado o Pro), elige una recomendada y luego podrás editar "
                "manualmente asegurado, patente y vehículo en la pantalla siguiente."
            )
            role_labels_for_mode = QUOTE_ROLE_LABELS
            role_keys_for_mode = QUOTE_ROLE_KEYS
        else:
            st.caption(
                "Asigna el rol correcto de cada documento (Básico, Equilibrado o Pro identifica la columna y la etiqueta "
                "comercial en el PDF). Si el cliente no tiene seguro vigente, no marques ningún archivo como "
                "'Póliza actual' (al menos tres cotizaciones son obligatorias). "
                "En cada cotización el comparativo usa la modalidad de **11 cuotas** del PDF cuando consta."
            )
            role_labels_for_mode = ROLE_LABELS
            role_keys_for_mode = ROLE_KEYS

        roles: list[str] = []
        restored_roles = list(st.session_state.get("roles") or [])

        cols_header = st.columns([3, 2])
        cols_header[0].markdown("**Archivo**")
        cols_header[1].markdown("**Rol**")

        for idx, file_name in enumerate(file_display_names):
            c_name, c_role = st.columns([3, 2])
            c_name.write(file_name)

            default_idx = min(idx, len(role_labels_for_mode) - 1)
            if case_mode == CASE_MODE_CURRENT and idx == 0 and n_files > 3:
                default_idx = 0
            elif case_mode == CASE_MODE_CURRENT:
                default_idx = min(idx + 1, len(role_labels_for_mode) - 1)
            if idx < len(restored_roles) and restored_roles[idx] in role_keys_for_mode:
                default_idx = role_keys_for_mode.index(restored_roles[idx])

            role_label = c_role.selectbox(
                f"Rol #{idx+1}",
                role_labels_for_mode,
                index=default_idx,
                key=f"role_{case_mode}_{idx}",
                label_visibility="collapsed",
            )
            role_key = role_keys_for_mode[role_labels_for_mode.index(role_label)]
            roles.append(role_key)

        quote_indices = [i for i, rk in enumerate(roles) if rk != "current_policy"]
        quote_count = len(quote_indices)
        current_count = len(roles) - quote_count
        if case_mode == CASE_MODE_QUOTES_ONLY_4:
            roles_ok = quote_count == 4 and n_files == 4
        else:
            roles_ok = quote_count >= 3 and current_count <= 1

        winner_idx: int | None = None
        if quote_indices:
            winner_key = f"upload_winner_file_idx_{case_mode}"
            if st.session_state.get(winner_key) not in quote_indices:
                restored_winner = st.session_state.get("winner_idx")
                st.session_state[winner_key] = (
                    restored_winner if restored_winner in quote_indices else quote_indices[0]
                )
            winner_idx = st.radio(
                "Cotización ganadora (elige una)",
                options=quote_indices,
                format_func=lambda i: file_display_names[i],
                horizontal=True,
                key=winner_key,
            )
        else:
            st.info("Marca al menos un archivo como cotización (cualquier rol distinto de 'Póliza actual').")

        if case_mode == CASE_MODE_QUOTES_ONLY_4 and (quote_count != 4 or n_files != 4):
            st.info("En este modo carga exactamente 4 PDFs y marca los 4 como cotizaciones.")
        elif quote_count < 3:
            st.info("Asigna al menos 3 archivos como cotización (Básico, Equilibrado o Pro).")
        elif current_count > 1:
            st.info("Marca como máximo un archivo como póliza actual.")

        run_clicked = st.button(
            "3) Iniciar Extracción Documental",
            type="primary",
            disabled=not roles_ok or winner_idx is None or st.session_state.get("run_status") == "running",
        )

        if run_clicked and roles_ok and winner_idx is not None:
            startup_notice = st.empty()
            startup_notice.info("Iniciando extracción documental... preparando archivos y conexión con OpenRouter.")
            _clear_generated_pdf_state()
            st.session_state.run_status = "running"
            st.session_state.run_error = ""
            st.session_state.run_stage = "Preparando corrida"
            winner_tier_internal = roles[winner_idx]
            offer_tier_overrides: dict[int, str] = {}
            winner_quote_position = None
            q_pos = 0
            for i, r in enumerate(roles):
                if r != "current_policy":
                    q_pos += 1
                    offer_tier_overrides[q_pos] = ROLE_DISPLAY[r]
                    if i == winner_idx:
                        winner_quote_position = q_pos

            st.session_state.winner_tier_internal = winner_tier_internal
            st.session_state.winner_quote_position = winner_quote_position
            st.session_state.offer_tier_overrides = offer_tier_overrides
            st.session_state.saved_paths = active_paths
            st.session_state.uploaded_file_display_names = file_display_names
            st.session_state.roles = roles
            st.session_state.winner_idx = winner_idx
            st.session_state.case_mode = case_mode
            _write_draft_state()

            # Prepare metrics
            session = SessionMetrics(model=model)
            session.start_timer()

            client = OpenRouterClient(model=model)
            try:
                st.session_state.run_stage = "Consultando configuración de modelos"
                client.fetch_model_prices()

                st.session_state.run_stage = "Obteniendo UF"
                try:
                    uf_ref = resolve_reference_uf(
                        manual_clp=uf_manual_clp if uf_manual_clp and uf_manual_clp > 0 else None,
                        manual_date=uf_manual_date.isoformat() if uf_manual_date else None,
                        fetch_online=True,
                    )
                except UFReferenceError as exc:
                    uf_ref = None
                    st.warning(
                        f"No se pudo obtener la UF automáticamente: {exc}. "
                        "Continuaré con la UF que aparezca en los PDFs; si quieres fijarla, "
                        "activa **Ingresar UF manualmente** en la barra lateral."
                    )
                if uf_ref is None:
                    st.warning(
                        "No hay una UF automática disponible. Continuaré con la UF detectada en los documentos."
                    )

                st.session_state.uf_ref = uf_ref
                _write_draft_state()

                num_pdfs = len(st.session_state.saved_paths)
                total_steps = num_pdfs + 1  # extracción por PDF + análisis final
                startup_notice.empty()
                on_step, complete_progress = _create_progress_tracker(total_steps)

                single_extractions = []
                for i, (path, role) in enumerate(zip(st.session_state.saved_paths, st.session_state.roles)):
                    st.session_state.run_stage = f"Extrayendo {path.name}"
                    on_step(f"Extrayendo {path.name}", i + 1, total_steps)
                    from src.pdf_reader import read_pdf
                    pdf_data = read_pdf(path)
                    doc_type = "current_policy" if role == "current_policy" else "quote"
                    from src.prompts import build_extraction_prompt
                    messages = build_extraction_prompt(
                        pdf_text=pdf_data["text"],
                        file_name=pdf_data["file_name"],
                        document_type=doc_type,
                        document_role=role,
                    )
                    resp_text, call_m = client.chat(messages=messages, step_name=f"extraction_{i+1}")
                    session.add_call(call_m)
                    try:
                        ext_json = _parse_json_response(resp_text)
                    except Exception:
                        ext_json = {"error": "Failed to parse JSON", "raw": resp_text[:500]}
                    single_extractions.append(ext_json)
                    st.session_state.resolved_extractions = single_extractions
                    _write_draft_state()

                st.session_state.run_stage = "Analizando caso completo"
                on_step("Analizando caso completo", num_pdfs + 1, total_steps)
                st.session_state.session_metrics = session.to_dict()
                _run_analysis_phase(client, session)
                analysis_ok = not (
                    isinstance(st.session_state.analysis, dict)
                    and st.session_state.analysis.get("error")
                )
                st.session_state.run_status = "completed" if analysis_ok else "failed"
                _write_draft_state()
                complete_progress(
                    "Extracción y análisis completados."
                    if analysis_ok
                    else "Extracción lista; el análisis falló (puedes reintentar abajo)."
                )
            except Exception as exc:
                _set_run_failed(st.session_state.get("run_stage") or "corrida", exc)
                st.session_state.analysis = {
                    "error": "run_failed",
                    "message": str(exc),
                }
                st.session_state.step = "editor"
                _write_draft_state()
            finally:
                client.close()
            st.rerun()

    # ------------------------------------------------------------------
    # STEP 2: ORDERLY FORM EDITOR & INSTANT PDF GENERATOR
    # ------------------------------------------------------------------
    elif st.session_state.step == "editor":
        st.subheader("3) Editar Datos de la Propuesta")
        st.caption(
            "El JSON se ha estructurado. Modifica los campos que desees en los acordeones a continuación "
            "y haz clic en **Generar PDF** para previsualizar o descargar el comparativo al instante sin volver a llamar a OpenRouter."
        )

        analysis = st.session_state.analysis
        if not _prepare_analysis_for_editor(analysis):
            detail = ""
            if isinstance(analysis, dict):
                detail = analysis.get("message") or analysis.get("raw") or analysis.get("error") or ""
            if st.session_state.resolved_extractions:
                st.error(
                    "El análisis final no se generó correctamente, pero las extracciones de los PDFs "
                    "quedaron guardadas. No necesitas volver a cargar los archivos."
                    + (f"\n\n{detail}" if detail else "")
                )
            else:
                st.error(
                    "El análisis no se generó correctamente. Vuelve a cargar los PDFs e intenta de nuevo."
                    + (f"\n\n{detail}" if detail else "")
                )
            if isinstance(analysis, dict) and analysis.get("raw"):
                with st.expander("Detalle del error"):
                    st.code(str(analysis.get("raw", analysis))[:2000])
            if st.session_state.resolved_extractions:
                st.info(
                    "Las extracciones de los PDFs quedaron guardadas en esta sesión. "
                    "Puedes reintentar solo el análisis final sin volver a cargar los archivos. "
                    "Si el error fue límite temporal de OpenRouter, espera 1-2 minutos antes de reintentar."
                )
                if st.button("Reintentar análisis", type="primary"):
                    _retry_analysis_from_current_extractions()
                    st.rerun()
            st.stop()

        # 1. Metadatos y Asegurado
        with st.expander("Asegurado, Vehículo e Información de UF", expanded=True):
            col_ins_1, col_ins_2 = st.columns(2)
            with col_ins_1:
                insured_name = st.text_input("Nombre Asegurado", _get_val(analysis["insured"].get("name")))
                _set_val(analysis["insured"]["name"], insured_name)

                vehicle_display = st.text_input("Modelo del Vehículo (Display)", _get_val(analysis["insured"].get("vehicle_display_name")))
                _set_val(analysis["insured"]["vehicle_display_name"], vehicle_display)

                plate = st.text_input("Patente", _get_val(analysis["insured"].get("plate")))
                _set_val(analysis["insured"]["plate"], plate)
            with col_ins_2:
                make = st.text_input("Marca", _get_val(analysis["insured"].get("vehicle_make")))
                _set_val(analysis["insured"]["vehicle_make"], make)

                v_model = st.text_input("Modelo", _get_val(analysis["insured"].get("vehicle_model")))
                _set_val(analysis["insured"]["vehicle_model"], v_model)

                v_year = st.number_input("Año", value=int(parse_chilean_number(_get_val(analysis["insured"].get("vehicle_year"))) or date.today().year), step=1)
                _set_val(analysis["insured"]["vehicle_year"], v_year)

                usage = st.text_input("Uso", _get_val(analysis["insured"].get("usage")))
                _set_val(analysis["insured"]["usage"], usage)

            st.markdown("##### Variables Financieras")
            col_meta_1, col_meta_2, col_meta_3 = st.columns(3)
            with col_meta_1:
                uf_val = st.number_input("Valor de la UF", value=float(analysis["context"].get("uf_value_used") or 40000.0), format="%.2f")
                analysis["context"]["uf_value_used"] = uf_val
            with col_meta_2:
                uf_date_str = st.text_input("Fecha Referencia UF", analysis["context"].get("uf_reference_date") or date.today().isoformat())
                analysis["context"]["uf_reference_date"] = uf_date_str
            with col_meta_3:
                base_deductible = st.number_input("Deducible Comparativo (UF)", value=float(analysis["context"].get("base_deductible_uf") or 10.0), step=1.0)
                analysis["context"]["base_deductible_uf"] = base_deductible

        # 2. Póliza Actual (si existe)
        if analysis.get("current_policy"):
            current = analysis["current_policy"]
            with st.expander("Tu Seguro Hoy (Póliza Actual)", expanded=False):
                col_curr_1, col_curr_2, col_curr_3 = st.columns(3)
                with col_curr_1:
                    c_insurer = st.text_input("Aseguradora Actual", _get_val(current.get("insurer")))
                    _set_val(current["insurer"], c_insurer)

                    c_product = st.text_input("Plan Actual", _get_val(current.get("product_name")))
                    _set_val(current["product_name"], c_product)
                with col_curr_2:
                    c_ded = st.number_input("Deducible Actual (UF)", value=float(parse_chilean_number(_get_val(current.get("deductible_uf"))) or 0.0), step=1.0)
                    _set_val(current["deductible_uf"], c_ded)

                    c_prem_uf = st.number_input("Prima Mensual Actual (UF)", value=float(parse_chilean_number(_get_val(current.get("monthly_premium_uf"))) or 0.0), step=0.01)
                    _set_val(current["monthly_premium_uf"], c_prem_uf)
                with col_curr_3:
                    c_prem_clp = st.number_input("Prima Mensual Actual (CLP)", value=int(parse_chilean_number(_get_val(current.get("monthly_premium_clp"))) or 0), step=100)
                    _set_val(current["monthly_premium_clp"], c_prem_clp)

                st.markdown("##### Coberturas Póliza Actual")
                col_cc_1, col_cc_2, col_cc_3 = st.columns(3)
                with col_cc_1:
                    curr_rc = st.text_input("RC Combinada", _get_summary_val(current.get("rc")))
                    _set_summary_val(current["rc"], curr_rc)

                    curr_rc_em = st.text_input("RC Emergente", _get_summary_val(current.get("rc_emergente")))
                    _set_summary_val(current["rc_emergente"], curr_rc_em)

                    curr_rc_mo = st.text_input("RC Daño Moral", _get_summary_val(current.get("rc_moral")))
                    _set_summary_val(current["rc_moral"], curr_rc_mo)

                    curr_rc_lc = st.text_input("RC Lucro Cesante", _get_summary_val(current.get("rc_lucro_cesante")))
                    _set_summary_val(current["rc_lucro_cesante"], curr_rc_lc)

                    curr_rc_exc = st.text_input("RC en Exceso", _get_summary_val(current.get("rc_exceso")))
                    _set_summary_val(current["rc_exceso"], curr_rc_exc)
                with col_cc_2:
                    curr_rep = st.text_input("Auto Reemplazo", _get_summary_val(current.get("auto_replacement")))
                    _set_summary_val(current["auto_replacement"], curr_rep)

                    curr_cop = st.text_input("Copago Auto Reemplazo", _get_summary_val(current.get("copago_reemplazo")))
                    _set_summary_val(current["copago_reemplazo"], curr_cop)

                    curr_ws = st.text_input("Taller", _get_summary_val(current.get("workshop")))
                    _set_summary_val(current["workshop"], curr_ws)

                    curr_rep_n = st.text_input("Reposición Nuevo", _get_summary_val(current.get("reposicion_a_nuevo")))
                    _set_summary_val(current["reposicion_a_nuevo"], curr_rep_n)
                with col_cc_3:
                    curr_pt = st.text_input("Umbral Pérdida Total", _get_summary_val(current.get("perdida_total")))
                    _set_summary_val(current["perdida_total"], curr_pt)

                    curr_ast = st.text_input("Asistencia", _get_summary_val(current.get("assistance")))
                    _set_summary_val(current["assistance"], curr_ast)

                    curr_pas = st.text_input("Asiento Pasajeros", _get_summary_val(current.get("asiento_pasajeros")))
                    _set_summary_val(current["asiento_pasajeros"], curr_pas)

                    curr_def = st.text_input("Defensa Penal", _get_summary_val(current.get("defensa_penal")))
                    _set_summary_val(current["defensa_penal"], curr_def)

        # 3. Ofertas de Cotización (Básico, Equilibrado, Pro)
        has_current_policy = bool(analysis.get("current_policy"))
        for o_idx, offer in enumerate(analysis.get("offers", [])):
            ins = _get_val(offer.get("insurer")).strip()
            prod = _get_val(offer.get("product_name")).strip()
            title = f"{ins} — {prod}".strip(" —") or f"Cotización #{o_idx + 1}"
            with st.expander(f"Oferta #{o_idx + 1}: {title}", expanded=False):
                col_o_1, col_o_2, col_o_3 = st.columns(3)
                with col_o_1:
                    o_insurer = st.text_input(f"Aseguradora #{o_idx+1}", _get_val(offer.get("insurer")), key=f"o_ins_{o_idx}")
                    _set_val(offer["insurer"], o_insurer)

                    o_product = st.text_input(f"Plan #{o_idx+1}", _get_val(offer.get("product_name")), key=f"o_prod_{o_idx}")
                    _set_val(offer["product_name"], o_product)
                with col_o_2:
                    o_ded = st.number_input(f"Deducible Comparado (UF) #{o_idx+1}", value=float(parse_chilean_number(_get_val(offer.get("comparison_deductible_uf"))) or 0.0), step=1.0, key=f"o_ded_{o_idx}")
                    _set_val(offer["comparison_deductible_uf"], o_ded)

                    o_prem_uf = st.number_input(f"Prima Mensual Comparada (UF) #{o_idx+1}", value=float(parse_chilean_number(_get_val(offer.get("monthly_premium_uf"))) or 0.0), step=0.01, key=f"o_p_uf_{o_idx}")
                    _set_val(offer["monthly_premium_uf"], o_prem_uf)

                    o_prem_clp = st.number_input(f"Prima Mensual Comparada (CLP) #{o_idx+1}", value=int(parse_chilean_number(_get_val(offer.get("monthly_premium_clp"))) or 0), step=100, key=f"o_p_clp_{o_idx}")
                    _set_val(offer["monthly_premium_clp"], o_prem_clp)
                with col_o_3:
                    o_pay = st.text_input(f"Medio de Pago #{o_idx+1}", _get_val(offer.get("payment_method")), key=f"o_pay_{o_idx}")
                    _set_val(offer["payment_method"], o_pay)

                    o_inst = st.number_input(f"Cuotas #{o_idx+1}", value=int(parse_chilean_number(_get_val(offer.get("installments"))) or 12), step=1, key=f"o_inst_{o_idx}")
                    _set_val(offer["installments"], o_inst)

                    savings_label = (
                        f"Ahorro Mensual vs Hoy (CLP) #{o_idx+1}"
                        if has_current_policy
                        else f"Diferencia Referencial (CLP) #{o_idx+1}"
                    )
                    o_sav = st.number_input(savings_label, value=int(parse_chilean_number(_get_val(offer.get("monthly_savings_vs_current_clp"))) or 0), step=100, key=f"o_sav_{o_idx}")
                    _set_val(offer["monthly_savings_vs_current_clp"], o_sav)

                st.markdown(f"##### Coberturas Oferta #{o_idx+1}")
                cov_names = [
                    ("rc", "RC Combinada"),
                    ("rc_emergente", "RC Emergente"),
                    ("rc_moral", "RC Daño Moral"),
                    ("rc_lucro_cesante", "RC Lucro Cesante"),
                    ("rc_exceso", "RC en Exceso"),
                    ("auto_replacement", "Auto Reemplazo"),
                    ("copago_reemplazo", "Copago Auto Reemplazo"),
                    ("workshop", "Taller"),
                    ("reposicion_a_nuevo", "Reposición Nuevo"),
                    ("perdida_total", "Umbral Pérdida Total"),
                    ("assistance", "Asistencia"),
                    ("asiento_pasajeros", "Asiento Pasajeros"),
                    ("defensa_penal", "Defensa Penal"),
                ]

                # Render 4 columns for coverages grid
                grid_cols = st.columns(3)
                for c_num, (c_key, c_title) in enumerate(cov_names):
                    g_idx = c_num % 3
                    with grid_cols[g_idx]:
                        val_input = st.text_input(f"{c_title} #{o_idx+1}", _get_summary_val(offer.get(c_key)), key=f"o_val_{c_key}_{o_idx}")
                        _set_summary_val(offer[c_key], val_input)

                        label_input = st.selectbox(f"Comparación {c_title} #{o_idx+1}", ["MEJORA", "IGUAL", "PEOR", "MIXTO"], index=["MEJORA", "IGUAL", "PEOR", "MIXTO"].index(_get_label_val(offer.get(c_key))), key=f"o_lab_{c_key}_{o_idx}")
                        _set_label_val(offer[c_key], label_input)
                        st.markdown("<br>", unsafe_allow_html=True)

                st.markdown(f"##### Extras y Resumen Oferta #{o_idx+1}")
                col_e_1, col_o_summary = st.columns(2)
                with col_e_1:
                    st.write("**Extras Destacados**")
                    extras = offer.setdefault("extra_highlights", [])
                    # Render 4 inputs for extras
                    for ex_idx in range(4):
                        existing_ex = _get_val(extras[ex_idx]) if ex_idx < len(extras) else ""
                        ex_val = st.text_input(f"Extra #{ex_idx+1} (Oferta #{o_idx+1})", existing_ex, key=f"extra_hi_{o_idx}_{ex_idx}")
                        if ex_idx < len(extras):
                            _set_val(extras[ex_idx], ex_val)
                        else:
                            if ex_val.strip():
                                extras.append({"value": ex_val.strip(), "confidence": 1.0, "method": "manual"})
                with col_o_summary:
                    o_ed_sum = st.text_area(f"En Simple (Tesis Comercial) #{o_idx+1}", _get_val(offer.get("editorial_summary")), height=120, key=f"o_ed_sum_{o_idx}")
                    _set_val(offer["editorial_summary"], o_ed_sum)

                # Deductible Options table (for offer deductible list)
                st.markdown(f"##### Tabla de Deducibles Alternativos (Oferta #{o_idx+1})")
                ded_opts = offer.setdefault("deductible_options", [])

                # We render 4 rows
                for row_idx in range(4):
                    row_cols = st.columns(5)
                    if row_idx < len(ded_opts):
                        opt = ded_opts[row_idx]
                    else:
                        opt = {"deductible_uf": 0.0, "monthly_premium_uf": 0.0, "monthly_premium_clp": 0, "is_same_as_current": False, "is_proposed": False}

                    with row_cols[0]:
                        d_uf = st.number_input(f"Ded UF (Fila {row_idx+1}, #{o_idx+1})", value=float(opt.get("deductible_uf", 0.0)), step=1.0, key=f"ded_uf_opt_{o_idx}_{row_idx}")
                    with row_cols[1]:
                        p_uf = st.number_input(f"Prem UF (Fila {row_idx+1}, #{o_idx+1})", value=float(opt.get("monthly_premium_uf", 0.0)), step=0.01, key=f"prem_uf_opt_{o_idx}_{row_idx}")
                    with row_cols[2]:
                        p_clp = st.number_input(f"Prem CLP (Fila {row_idx+1}, #{o_idx+1})", value=int(opt.get("monthly_premium_clp", 0)), step=100, key=f"prem_clp_opt_{o_idx}_{row_idx}")
                    with row_cols[3]:
                        same_label = (
                            f"Mismo ded. hoy (Fila {row_idx+1}, #{o_idx+1})"
                            if has_current_policy
                            else f"Deducible referencia (Fila {row_idx+1}, #{o_idx+1})"
                        )
                        same_curr = st.checkbox(same_label, value=bool(opt.get("is_same_as_current", False)), key=f"same_curr_opt_{o_idx}_{row_idx}")
                    with row_cols[4]:
                        prop = st.checkbox(f"Propuesta (Fila {row_idx+1}, #{o_idx+1})", value=bool(opt.get("is_proposed", False)), key=f"prop_opt_{o_idx}_{row_idx}")

                    new_opt = {
                        "deductible_uf": d_uf,
                        "monthly_premium_uf": p_uf,
                        "monthly_premium_clp": p_clp,
                        "is_same_as_current": same_curr,
                        "is_proposed": prop
                    }
                    if row_idx < len(ded_opts):
                        ded_opts[row_idx] = new_opt
                    else:
                        if d_uf > 0 or p_uf > 0:
                            ded_opts.append(new_opt)

        # 4. Recomendación y Pie
        with st.expander("Recomendación, Insight Principal y Firma", expanded=False):
            headline = st.text_input("Franja Verde (Insight Principal)", _get_val(analysis["recommendation"].get("headline_insight")))
            _set_val(analysis["recommendation"]["headline_insight"], headline)

            reason = st.text_area("Resumen del Motivo de Recomendación", _get_val(analysis["recommendation"].get("reason_summary")), height=80)
            _set_val(analysis["recommendation"]["reason_summary"], reason)

            st.markdown("##### Pie de Página y Firma")
            col_firm_1, col_firm_2 = st.columns(2)
            with col_firm_1:
                broker_name = st.text_input("Nombre Firma Corredor", analysis["footer"].get("broker_name") or "Convision Corredores de Seguros SpA")
                analysis["footer"]["broker_name"] = broker_name
            with col_firm_2:
                broker_site = st.text_input("Sitio Web", analysis["footer"].get("broker_website") or "www.convision.cl")
                analysis["footer"]["broker_website"] = broker_site

        # ------------------------------------------------------------------
        # GENERATE AND DOWNLOAD REFCAR PDF
        # ------------------------------------------------------------------
        st.divider()
        st.subheader("4) Generar Comparativo en PDF")

        col_gen_1, col_gen_2 = st.columns([1, 4])
        with col_gen_1:
            gen_clicked = st.button("Generar PDF", type="primary", use_container_width=True)

        if gen_clicked:
            with st.spinner("Compilando plantilla HTML y renderizando PDF de Refcar..."):
                pdf_output = RUNS_DIR / "generated_latest.pdf"

                # Call renderer
                generated_pdf_path = generate_summary_pdf(
                    analysis=st.session_state.analysis,
                    output_path=pdf_output,
                    selected_tier=st.session_state.winner_tier_internal,
                    offer_tier_overrides=st.session_state.offer_tier_overrides,
                )
                pdf_bytes = generated_pdf_path.read_bytes()
                st.session_state.pdf_bytes = pdf_bytes

                # Save historical run
                run_file = save_run(
                    model=str(st.session_state.session_metrics.get("model") or DEFAULT_PRIMARY_MODEL),
                    selected_tier=st.session_state.winner_tier_internal,
                    pdf_names=_current_pdf_display_names(),
                    metrics=st.session_state.session_metrics,
                    result={"extractions": st.session_state.resolved_extractions, "analysis": st.session_state.analysis},
                    case_mode=st.session_state.case_mode,
                    generated_pdf_path=str(generated_pdf_path),
                )
                st.session_state.run_file_name = run_file.name
                st.session_state.run_file_stem = run_file.stem

        if "pdf_bytes" in st.session_state:
            st.success("PDF comparativo de Refcar compilado exitosamente.")

            # Show download button
            st.download_button(
                "📥 Descargar PDF Comparativo",
                data=st.session_state.pdf_bytes,
                file_name=f"comparativo_{st.session_state.run_file_stem}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )

def _retry_analysis_from_current_extractions() -> None:
    model = str(st.session_state.session_metrics.get("model") or DEFAULT_PRIMARY_MODEL)
    session = SessionMetrics.from_dict(st.session_state.session_metrics)
    session.model = model
    client = OpenRouterClient(model=model)
    try:
        st.session_state.run_status = "running"
        st.session_state.run_error = ""
        st.session_state.run_stage = "Reintentando análisis"
        with st.spinner("Reintentando análisis final con las extracciones ya realizadas..."):
            client.fetch_model_prices()
            _run_analysis_phase(client, session)
    except Exception as exc:
        _set_run_failed("analysis_retry", exc)
        st.session_state.analysis = {
            "error": "openrouter_failed",
            "message": str(exc),
        }
        st.session_state.step = "editor"
        _write_draft_state()
    finally:
        client.close()


def _run_analysis_phase(client: OpenRouterClient, session: SessionMetrics):
    # Inyectar UF
    uf_clp = None
    uf_date = None
    if st.session_state.uf_ref:
        uf_clp, uf_date = st.session_state.uf_ref[0], st.session_state.uf_ref[1]

    # Clean extractions for prompt
    clean_extractions = []
    for ext in st.session_state.resolved_extractions:
        clean = {k: v for k, v in ext.items() if k != "_validation_errors"}
        clean_extractions.append(clean)

    messages = build_analysis_prompt(
        clean_extractions,
        st.session_state.winner_tier_internal,
        uf_clp=uf_clp,
        uf_date=uf_date,
        case_mode=st.session_state.case_mode,
        recommended_position=st.session_state.get("winner_quote_position"),
    )

    try:
        response_text, call_metrics = client.chat(
            messages=messages,
            step_name="analysis",
        )
    except RuntimeError as exc:
        st.error(str(exc))
        _set_run_failed("analysis", exc)
        st.session_state.analysis = {
            "error": "openrouter_failed",
            "message": str(exc),
        }
        st.session_state.step = "editor"
        _write_draft_state()
        return

    session.add_call(call_metrics)
    st.session_state.session_metrics = session.to_dict()

    try:
        analysis = _parse_json_response(response_text)
    except json.JSONDecodeError:
        analysis = {"error": "Failed to parse JSON", "raw": response_text[:500]}

    if (
        st.session_state.uf_ref
        and isinstance(analysis, dict)
        and analysis.get("error") is None
    ):
        from src.uf_reference import apply_canonical_uf
        apply_canonical_uf(analysis, st.session_state.uf_ref[0], st.session_state.uf_ref[1])

    st.session_state.analysis = analysis
    st.session_state.run_status = (
        "failed"
        if isinstance(analysis, dict) and analysis.get("error")
        else "completed"
    )
    st.session_state.step = "editor"
    _write_draft_state()


if __name__ == "__main__":
    main()
