from __future__ import annotations

from datetime import datetime
from dateutil import parser as dateparser

def parse_datetime_safe(value: str) -> str | None:
    """
    Pokúsi sa parsovať dátum/čas do ISO 8601.
    Vracia ISO string alebo None.
    """
    if not value:
        return None
    try:
        dt = dateparser.parse(value, dayfirst=True, fuzzy=True)
        if not dt:
            return None
        return dt.isoformat()
    except Exception:
        return None

def normalize_added_date(text: str) -> str | None:
    """
    Pre texty typu 'PRIDANÉ: 25.12.2025' sa pokúsi vybrať dátum.
    """
    if not text:
        return None
    # necháme dateutil spraviť fuzzy parsing
    return parse_datetime_safe(text)
