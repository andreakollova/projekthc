from __future__ import annotations

import re
from bs4 import BeautifulSoup

# Použijeme rovnaký regex ako inde – nie je nutný, ale hodí sa, keby bol button inak popísaný.
_REPORT_TEXT_RE = re.compile(r"^\s*report\s*$", re.IGNORECASE)


def _abs_url(base_url: str, href: str) -> str:
    href = (href or "").strip()
    if not href:
        return href
    if href.startswith("http"):
        return href
    if href.startswith("//"):
        return "https:" + href
    if href.startswith("/"):
        return base_url.rstrip("/") + href
    return base_url.rstrip("/") + "/" + href


def _build_match_key(date_iso: str | None, date_text: str | None, round_text: str | None,
                     team_home: str | None, team_away: str | None) -> str:
    """
    match_key MUSÍ byť identický ako v parsers/zapasy_api.py:
    key_date|round|home|away (bez statusu)
    """
    key_date = ((date_iso or "").strip() or (date_text or "").strip())
    key_round = (round_text or "").strip()
    key_home = (team_home or "").strip()
    key_away = (team_away or "").strip()
    return "|".join([key_date, key_round, key_home, key_away]).strip("|")


def parse_report_links(html: str, base_url: str) -> dict[str, str]:
    """
    Vráti mapu: match_key -> report_url

    Berie to z HTML listu zápasov, kde je button "Report" ako <a href="...">Report</a>
    a priraďuje ho podľa rovnakého match_key ako API (bez statusu).
    """
    soup = BeautifulSoup(html, "lxml")
    out: dict[str, str] = {}

    for item in soup.select(".matches-list__item"):
        # --- dátum ---
        time_el = item.select_one("time.matches-list__date")
        date_text = time_el.get_text(" ", strip=True) if time_el else None
        date_iso = (time_el.get("datetime") or "").strip() if (time_el and time_el.get("datetime")) else None

        # --- kolo ---
        round_el = item.select_one(".matches-list__round")
        round_text = round_el.get_text(" ", strip=True) if round_el else None

        # --- tímové názvy ---
        team_names = [
            x.get_text(" ", strip=True)
            for x in item.select(".matches-list__team-names > .matches-list__team-name")
        ]
        team_home = team_names[0] if len(team_names) > 0 else None
        team_away = team_names[1] if len(team_names) > 1 else None

        match_key = _build_match_key(date_iso, date_text, round_text, team_home, team_away)
        if not match_key:
            continue

        # --- report link ---
        # Na webe býva: <div class="matches-list__button ..."><a href="...">Report</a></div>
        a_tags = item.select(".matches-list__button a[href]")
        if not a_tags:
            continue

        report_url = None
        for a in a_tags:
            txt = a.get_text(" ", strip=True) or ""
            if _REPORT_TEXT_RE.match(txt):
                report_url = _abs_url(base_url, a.get("href") or "")
                break

        if report_url:
            out[match_key] = report_url

    return out
