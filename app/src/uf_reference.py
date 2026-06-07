"""Resolución de la UF en pesos (CLP) para normalizar cotizaciones y el PDF."""

from __future__ import annotations

import os
from datetime import date, datetime

import httpx


class UFReferenceError(Exception):
    """No se pudo obtener un valor válido de UF."""


_MINDICADOR_UF_URL = "https://mindicador.cl/api/uf"


def fetch_uf_latest_mindicador(timeout_s: float = 12.0) -> tuple[float, str]:
    """Obtiene la última serie publicada por mindicador.cl (tercero público).

    La UF oficial se publica en el Banco Central de Chile; muchos desarrolladores
    usan este endpoint para consultas de referencia. Para uso formal conviene o bien
    fijar `UF_REFERENCE_CLP` en `.env`, o cargar desde tu propio servicio institucional.
    """
    try:
        with httpx.Client(timeout=timeout_s) as client:
            resp = client.get(_MINDICADOR_UF_URL)
            resp.raise_for_status()
            data = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise UFReferenceError("no se pudo consultar mindicador.cl") from exc
    serie = data.get("serie") or []
    if not serie:
        raise UFReferenceError("mindicador.cl devolvió una serie UF vacía")
    latest = serie[0]
    valor = latest.get("valor")
    fecha = latest.get("fecha")
    if valor is None or fecha is None:
        raise UFReferenceError("Respuesta incompleta de mindicador.cl")
    try:
        clp_per_uf = float(valor)
    except (TypeError, ValueError) as exc:
        raise UFReferenceError("Valor UF inválido en API") from exc
    fecha_str = _iso_date_only(str(fecha))
    return clp_per_uf, fecha_str


def uf_from_env() -> tuple[float | None, str | None]:
    """Lee UF desde variables de entorno `UF_REFERENCE_CLP` y `UF_REFERENCE_DATE` (YYYY-MM-DD)."""
    raw = os.getenv("UF_REFERENCE_CLP", "").strip()
    dt_raw = os.getenv("UF_REFERENCE_DATE", "").strip()
    if not raw:
        return None, None
    try:
        clp = float(raw.replace(",", "."))
    except ValueError:
        return None, None
    if clp <= 0:
        return None, None
    # Fecha opcional; si falta, hoy en Chile se aproxima con fecha local del servidor
    if dt_raw:
        return clp, dt_raw[:10]
    return clp, date.today().isoformat()


def resolve_reference_uf(
    *,
    manual_clp: float | None,
    manual_date: str | None,
    fetch_online: bool = True,
) -> tuple[float, str] | None:
    """Decide qué UF usar.

    Prioridad:
    1. Valor manual del usuario (Streamlit) si `manual_clp` > 0.
    2. Si `fetch_online` es True, consulta mindicador.cl.
    3. Si la consulta falla, usa `UF_REFERENCE_CLP` / `UF_REFERENCE_DATE`
       como respaldo si están configuradas en el entorno.
    4. None — el modelo infiere desde los PDFs (comportamiento anterior).
    """
    if manual_clp is not None and manual_clp > 0:
        d = (manual_date or date.today().isoformat())[:10]
        return float(manual_clp), d

    want_fetch = fetch_online or os.getenv(
        "FETCH_UF_ONLINE", ""
    ).strip().lower() in ("1", "true", "yes")
    if want_fetch:
        try:
            return fetch_uf_latest_mindicador()
        except UFReferenceError:
            env_clp, env_date = uf_from_env()
            if env_clp is not None:
                return env_clp, env_date or date.today().isoformat()
            raise

    env_clp, env_date = uf_from_env()
    if env_clp is not None:
        return env_clp, env_date or date.today().isoformat()

    return None


def apply_canonical_uf(analysis: dict, uf_clp: float, uf_date_iso: str) -> None:
    """Ajusta `context` y recalcula montos CLP mensuales en base a una única UF.

    Modifica `analysis` in-place. No falla si faltan campos.
    """
    ctx = analysis.get("context")
    if not isinstance(ctx, dict):
        analysis["context"] = {}
        ctx = analysis["context"]
    ctx["uf_value_used"] = uf_clp
    ctx["uf_reference_date"] = uf_date_iso[:10]

    current = analysis.get("current_policy")
    cur_clp = _rescale_current_policy(current, uf_clp)
    offers = analysis.get("offers")
    if not isinstance(offers, list):
        return
    for offer in offers:
        if not isinstance(offer, dict):
            continue
        _rescale_offer(offer, uf_clp, cur_clp)


def _iso_date_only(isoish: str) -> str:
    """Devuelve YYYY-MM-DD desde un ISO string."""
    isoish = isoish.strip()
    if len(isoish) >= 10 and isoish[4] == "-":
        return isoish[:10]
    try:
        if isoish.endswith("Z"):
            dt = datetime.fromisoformat(isoish.replace("Z", "+00:00"))
        else:
            dt = datetime.fromisoformat(isoish)
        return dt.date().isoformat()
    except ValueError:
        return date.today().isoformat()


def _derived_float(df: dict | None) -> float | None:
    if not isinstance(df, dict):
        return None
    return _parse_float_loose(df.get("value"))


def _parse_float_loose(raw) -> float | None:
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    s = str(raw).strip().replace(" ", "").replace("UF", "").replace("uf", "")
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _set_derived_int(target: dict, key: str, n: int) -> None:
    node = target.get(key)
    if isinstance(node, dict):
        node["value"] = n
    else:
        target[key] = {"value": n, "confidence": 0.95, "method": "rule"}


def _rescale_current_policy(current: dict | None, uf_clp: float) -> int | None:
    if not isinstance(current, dict):
        return None
    muf = _derived_float(current.get("monthly_premium_uf"))
    if muf is not None:
        clp = int(round(muf * uf_clp))
        _set_derived_int(current, "monthly_premium_clp", clp)
        return clp
    cp = _derived_float(current.get("monthly_premium_clp"))
    if cp is not None:
        return int(round(cp))
    return None


def _rescale_offer(offer: dict, uf_clp: float, current_monthly_clp: int | None) -> None:
    muf = _derived_float(offer.get("monthly_premium_uf"))
    oclp: int | None = None
    if muf is not None:
        oclp = int(round(muf * uf_clp))
        _set_derived_int(offer, "monthly_premium_clp", oclp)
    else:
        v = _derived_float(offer.get("monthly_premium_clp"))
        if v is not None:
            oclp = int(round(v))

    for opt in offer.get("deductible_options") or []:
        if not isinstance(opt, dict):
            continue
        ouf = opt.get("monthly_premium_uf")
        if ouf is not None:
            try:
                x = float(str(ouf).replace(",", "."))
                opt["monthly_premium_clp"] = int(round(x * uf_clp))
            except (TypeError, ValueError):
                pass

    if current_monthly_clp is not None and oclp is not None:
        _set_derived_int(offer, "monthly_savings_vs_current_clp", current_monthly_clp - oclp)
