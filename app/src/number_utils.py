"""Helpers for parsing numbers shown in Chilean insurance documents."""

from __future__ import annotations

import re


def parse_chilean_number(s: str) -> float | None:
    """Parse decimal and thousands separators commonly found in Chilean PDFs."""
    if not s:
        return None
    cleaned = re.sub(r"[^\d.,\-]", "", s.strip())
    if not cleaned:
        return None

    if "." in cleaned and "," in cleaned:
        if cleaned.index(".") < cleaned.index(","):
            num_str = cleaned.replace(".", "").replace(",", ".")
        else:
            num_str = cleaned.replace(",", "")
    elif "," in cleaned:
        parts = cleaned.split(",")
        if len(parts) == 2 and len(parts[1]) == 3 and not (len(parts[0]) == 1 and parts[0] == "0"):
            num_str = cleaned.replace(",", "")
        else:
            num_str = cleaned.replace(",", ".")
    elif "." in cleaned:
        parts = cleaned.split(".")
        if len(parts) == 2 and len(parts[1]) == 3 and not (len(parts[0]) == 1 and parts[0] == "0"):
            num_str = cleaned.replace(".", "")
        else:
            num_str = cleaned
    else:
        num_str = cleaned

    try:
        return float(num_str)
    except ValueError:
        return None
