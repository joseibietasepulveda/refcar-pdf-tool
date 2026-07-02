"""Deterministic parser for deductible/premium pricing tables.

This module never hardcodes logic per insurer. It only recognizes two generic
*structural* shapes that repeatedly show up in the markdown tables produced by
`pdf_reader.convert_tables_to_markdown` (built from pdfplumber's table
extraction), regardless of which insurer issued the PDF:

- **compact table**: one data row with cells like
  ``"11 cuotas de UF 0,91 $37.134"`` under a header row whose cells declare the
  deductible for that column (``"UF 3"``, ``"UF 5"``, ``"SD"`` for zero, etc).
- **grid table**: a deductible header row (``"UF 0" | "UF 3" | ...``) followed
  by repeating blocks of rows, one block per payment modality, where the first
  row states the number of installments (``"11cuotas"``), the next row the CLP
  premium (``"$46.112"``) and the next row the UF premium (``"UF 1,13"``).

If a PDF's pricing table does not match either shape, the parser simply
returns no rows for it and callers must fall back to the LLM-provided values.
This keeps the tool free of per-insurer special cases while still fixing the
cases we can recognize deterministically (at zero extra LLM cost).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PricingRow:
    deductible_uf: float
    installments: int
    monthly_premium_uf: float
    monthly_premium_clp: int
    payment_method: str = ""


_DEDUCTIBLE_HEADER_RE = re.compile(r"^(?:UF\s*([\d.,]+)|SD)$", re.IGNORECASE)
_COMPACT_CELL_RE = re.compile(
    r"(\d+)\s*cuotas?\s*de\s*UF\s*([\d.,]+)\s*\$?\s*([\d.,]+)", re.IGNORECASE
)
_INSTALLMENTS_CELL_RE = re.compile(r"^(\d+)\s*cuotas?$", re.IGNORECASE)
_CLP_CELL_RE = re.compile(r"^\$\s*([\d.,]+)$")
_UF_CELL_RE = re.compile(r"^UF\s*([\d.,]+)$", re.IGNORECASE)


def _to_float_cl(raw: str) -> float:
    s = raw.strip().replace(" ", "")
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    return float(s)


def _to_int_clp(raw: str) -> int:
    """Parse a CLP amount that uses '.' as thousands separator (e.g. '37.134')."""
    return int(raw.strip().replace(".", "").replace(" ", ""))


def _split_markdown_row(line: str) -> list[str]:
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [cell.strip() for cell in line.split("|")]


_SEPARATOR_CELL_RE = re.compile(r"^:?-{2,}:?$")


def _is_separator_row(cells: list[str]) -> bool:
    """True for the markdown header/body divider row (e.g. '| --- | --- |')."""
    non_empty = [c for c in cells if c]
    return bool(non_empty) and all(_SEPARATOR_CELL_RE.match(c) for c in non_empty)


def _find_deductible_header(rows: list[list[str]]) -> dict[int, float] | None:
    """Find the first row that looks like a deductible header and map column index -> UF."""
    for row in rows:
        mapping: dict[int, float] = {}
        matched = 0
        for idx, cell in enumerate(row):
            if not cell:
                continue
            m = _DEDUCTIBLE_HEADER_RE.match(cell)
            if m:
                matched += 1
                mapping[idx] = _to_float_cl(m.group(1)) if m.group(1) else 0.0
        if matched >= 2:
            return mapping
    return None


def _parse_compact_table(rows: list[list[str]]) -> list[PricingRow]:
    header_map = _find_deductible_header(rows)
    if not header_map:
        return []
    results: list[PricingRow] = []
    for row in rows:
        for idx, ded in header_map.items():
            if idx >= len(row) or not row[idx]:
                continue
            m = _COMPACT_CELL_RE.search(row[idx])
            if not m:
                continue
            try:
                results.append(
                    PricingRow(
                        deductible_uf=ded,
                        installments=int(m.group(1)),
                        monthly_premium_uf=_to_float_cl(m.group(2)),
                        monthly_premium_clp=_to_int_clp(m.group(3)),
                    )
                )
            except (ValueError, TypeError):
                continue
    return results


def _parse_grid_table(rows: list[list[str]]) -> list[PricingRow]:
    header_map = _find_deductible_header(rows)
    if not header_map:
        return []
    results: list[PricingRow] = []
    i = 0
    n = len(rows)
    while i < n:
        row = rows[i]
        inst_hits: dict[int, re.Match] = {}
        for idx in header_map:
            if idx < len(row) and row[idx]:
                m = _INSTALLMENTS_CELL_RE.match(row[idx])
                if m:
                    inst_hits[idx] = m
        if len(inst_hits) >= 2 and i + 2 < n:
            clp_row = rows[i + 1]
            uf_row = rows[i + 2]
            payment_method = row[0].strip() if row and row[0] else ""
            for idx, m in inst_hits.items():
                clp_cell = clp_row[idx] if idx < len(clp_row) else ""
                uf_cell = uf_row[idx] if idx < len(uf_row) else ""
                clp_match = _CLP_CELL_RE.match(clp_cell)
                uf_match = _UF_CELL_RE.match(uf_cell)
                if not (clp_match and uf_match):
                    continue
                try:
                    results.append(
                        PricingRow(
                            deductible_uf=header_map[idx],
                            installments=int(m.group(1)),
                            monthly_premium_uf=_to_float_cl(uf_match.group(1)),
                            monthly_premium_clp=_to_int_clp(clp_match.group(1)),
                            payment_method=payment_method,
                        )
                    )
                except (ValueError, TypeError):
                    continue
            i += 3
            continue
        i += 1
    return results


def parse_pricing_rows_from_text(pdf_text: str) -> list[PricingRow]:
    """Parse every markdown table found in `pdf_text` and return recognizable pricing rows.

    Only the well-formed ``| cell | cell |`` markdown tables (appended by
    `pdf_reader.convert_tables_to_markdown`) are considered; free-flowing plain
    text extracted directly from the PDF page is ignored on purpose because it
    is not reliably column-aligned.
    """
    if not pdf_text:
        return []
    all_rows: list[PricingRow] = []
    current_table_rows: list[list[str]] = []

    def flush() -> None:
        if not current_table_rows:
            return
        all_rows.extend(_parse_compact_table(current_table_rows))
        all_rows.extend(_parse_grid_table(current_table_rows))

    for line in pdf_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            cells = _split_markdown_row(stripped)
            if _is_separator_row(cells):
                continue  # markdown header/body divider row, not real data
            current_table_rows.append(cells)
        else:
            if current_table_rows:
                flush()
                current_table_rows = []
    flush()
    return all_rows


def build_deductible_price_map(
    rows: list[PricingRow], preferred_installments: int = 11
) -> dict[float, PricingRow]:
    """Reduce raw pricing rows to one authoritative row per deductible.

    Prefers `preferred_installments` (11 cuotas by default, matching the
    project's comparison standard) and otherwise picks the closest available
    installment count.
    """
    by_deductible: dict[float, list[PricingRow]] = {}
    for row in rows:
        by_deductible.setdefault(round(row.deductible_uf, 2), []).append(row)

    result: dict[float, PricingRow] = {}
    for ded, options in by_deductible.items():
        preferred = [o for o in options if o.installments == preferred_installments]
        chosen = preferred[0] if preferred else min(
            options, key=lambda o: abs(o.installments - preferred_installments)
        )
        result[ded] = chosen
    return result


def available_common_deductibles(
    quote_pdf_texts: list[str], preferred_installments: int = 11
) -> list[float]:
    """Return deductibles (UF) present in the pricing table of every quote given.

    Quotes whose table could not be parsed deterministically are ignored when
    computing the intersection so a single messy PDF doesn't block the rest;
    if none can be parsed, returns an empty list.
    """
    per_quote_sets: list[set[float]] = []
    for text in quote_pdf_texts:
        rows = parse_pricing_rows_from_text(text)
        price_map = build_deductible_price_map(rows, preferred_installments)
        if price_map:
            per_quote_sets.append(set(price_map.keys()))

    if not per_quote_sets:
        return []
    common = set.intersection(*per_quote_sets) if len(per_quote_sets) > 1 else per_quote_sets[0]
    return sorted(common)


def deductible_coverage_by_value(
    quote_pdf_texts: list[str], preferred_installments: int = 11
) -> dict[float, int]:
    """For each deductible found in ANY quote, count in how many quotes it appears.

    Useful to offer the broker every deductible that at least one insurer
    actually quotes (e.g. 0/15/20 UF only offered by one company), instead of
    hiding it just because not every quote in the set has it.
    """
    coverage: dict[float, int] = {}
    for text in quote_pdf_texts:
        rows = parse_pricing_rows_from_text(text)
        price_map = build_deductible_price_map(rows, preferred_installments)
        for ded in price_map:
            coverage[ded] = coverage.get(ded, 0) + 1
    return coverage


def available_any_deductibles(
    quote_pdf_texts: list[str], preferred_installments: int = 11
) -> list[float]:
    """Return the union of deductibles (UF) found in any of the given quotes."""
    return sorted(deductible_coverage_by_value(quote_pdf_texts, preferred_installments).keys())


def available_any_deductibles_for_paths(
    quote_paths: list[Path], preferred_installments: int = 11
) -> tuple[list[float], dict[float, int]]:
    """Convenience wrapper: read each quote PDF and compute the union of deductibles.

    Returns `(sorted_deductibles, coverage_by_value)` where `coverage_by_value`
    tells how many of the given quotes actually offer that deductible, so the
    UI can warn when a chosen deductible isn't available for every offer.
    """
    from .pdf_reader import read_pdf

    texts: list[str] = []
    for path in quote_paths:
        try:
            texts.append(read_pdf(Path(path))["text"])
        except Exception:
            texts.append("")
    coverage = deductible_coverage_by_value(texts, preferred_installments)
    return sorted(coverage.keys()), coverage


def _set_derived_value(target: dict, key: str, value) -> None:
    """Set a value onto a plain field or a derivedField-shaped ({"value": ...}) field."""
    node = target.get(key)
    if isinstance(node, dict):
        node["value"] = value
        node["method"] = "rule_deterministic_pricing_table"
        node["confidence"] = 0.98
    else:
        target[key] = {"value": value, "confidence": 0.98, "method": "rule_deterministic_pricing_table"}


def _current_monthly_clp(analysis: dict) -> int | None:
    current = analysis.get("current_policy")
    if not isinstance(current, dict):
        return None
    node = current.get("monthly_premium_clp")
    val = node.get("value") if isinstance(node, dict) else node
    try:
        return int(round(float(val)))
    except (TypeError, ValueError):
        return None


def enforce_common_deductible(
    analysis: dict,
    quote_pdf_texts: list[str],
    target_deductible_uf: float,
    preferred_installments: int = 11,
) -> list[str]:
    """Overwrite each offer's price at `target_deductible_uf` using deterministic parsing.

    `quote_pdf_texts` must be ordered by offer `position` (1-based): the text
    at index 0 corresponds to the offer with ``position == 1``, etc. Offers
    whose source table can't be parsed deterministically are left untouched
    (the LLM-provided price stays); a warning is returned for each of those so
    the caller can surface it if useful.

    Returns a list of human-readable warnings (may be empty).
    """
    warnings: list[str] = []
    offers = analysis.get("offers")
    if not isinstance(offers, list) or target_deductible_uf is None:
        return warnings

    try:
        target = round(float(target_deductible_uf), 2)
    except (TypeError, ValueError):
        return warnings

    ctx = analysis.get("context")
    uf_value = ctx.get("uf_value_used") if isinstance(ctx, dict) else None
    current_clp = _current_monthly_clp(analysis)

    for offer in offers:
        if not isinstance(offer, dict):
            continue
        position = offer.get("position")
        if not isinstance(position, int) or position < 1 or position > len(quote_pdf_texts):
            warnings.append(
                f"No hay texto de PDF disponible para la oferta en posición {position!r}; "
                "se mantiene el precio entregado por el análisis."
            )
            continue

        rows = parse_pricing_rows_from_text(quote_pdf_texts[position - 1])
        price_map = build_deductible_price_map(rows, preferred_installments)
        match = price_map.get(target)
        if match is None:
            warnings.append(
                f"No se encontró el deducible {target_deductible_uf:g} UF en la tabla de precios de la "
                f"oferta en posición {position}; se mantiene el precio entregado por el análisis."
            )
            continue

        clp_value = int(round(match.monthly_premium_uf * uf_value)) if uf_value else match.monthly_premium_clp

        _set_derived_value(offer, "comparison_deductible_uf", match.deductible_uf)
        _set_derived_value(offer, "monthly_premium_uf", match.monthly_premium_uf)
        _set_derived_value(offer, "monthly_premium_clp", clp_value)
        _set_derived_value(offer, "installments", match.installments)

        if current_clp is not None:
            _set_derived_value(offer, "monthly_savings_vs_current_clp", current_clp - clp_value)

    return warnings
