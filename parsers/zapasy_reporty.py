# parsers/zapasy_reporty.py
from __future__ import annotations

import re
from bs4 import BeautifulSoup


def _norm(x: str | None) -> str | None:
    if x is None:
        return None
    s = str(x).strip()
    return s or None


def _norm_ws(s: str | None) -> str:
    return " ".join((s or "").strip().split())


def _norm_round(s: str | None) -> str:
    """
    Zjednotí formát kola:
    - odstráni extra whitespace
    - zjednotí bodky a medzery (napr. "36. kolo" vs "36.kolo")
    """
    t = _norm_ws(s)
    if not t:
        return ""
    t = t.replace(" .", ".").replace(". ", ".")
    t = re.sub(r"\s+", " ", t)
    return t.strip()


def _abs_url(base_url: str, href: str) -> str:
    href = (href or "").strip()
    if not href:
        return ""
    if href.startswith("http"):
        return href
    if href.startswith("//"):
        return "https:" + href
    if href.startswith("/"):
        return base_url.rstrip("/") + href
    return base_url.rstrip("/") + "/" + href


def _looks_like_report_href(href: str) -> bool:
    """
    Report na HK Košice typicky vyzerá ako:
      /a-muzstvo/zapasy/<slug>
    alebo môže obsahovať aj ďalšie segmenty, ale pointa je ".../zapasy/..."
    """
    h = (href or "").strip().lower()
    if not h:
        return False

    # najistejšie: sekcia zapasy články
    if "/a-muzstvo/zapasy/" in h:
        return True

    # fallback – keby mali iný tvar, ale stále obsahuje "/zapasy/" a nie je to samotný list
    if "/zapasy/" in h and not h.endswith("/zapasy") and not h.endswith("/zapasy/"):
        return True

    return False


def parse_match_reports(html: str, base_url: str) -> list[dict]:
    """
    Vytiahne report_url z HTML stránky zápasov.
    Vracia list dictov:
      {
        "match_key": "...",
        "match_key_swapped": "...",
        "match_key_noround": "...",
        "match_key_noround_swapped": "...",
        "report_url": "..."
      }

    match_key štýl:
      key_date|key_round|home|away
    kde key_date berieme prioritne z time[datetime], fallback z textu.
    """
    soup = BeautifulSoup(html, "lxml")
    out: list[dict] = []

    for item in soup.select(".matches-list__item"):
        # --- report link: nehľadaj podľa textu, ale podľa href patternu ---
        report_a = None
        for a in item.select("a[href]"):
            href = (a.get("href") or "").strip()
            if _looks_like_report_href(href):
                report_a = a
                break

        if not report_a:
            continue

        report_url = _abs_url(base_url, report_a.get("href") or "")
        if not report_url:
            continue

        # --- date ---
        time_el = item.select_one("time.matches-list__date")
        date_text = _norm(time_el.get_text(" ", strip=True) if time_el else None)
        date_iso = _norm(time_el.get("datetime") if time_el else None)

        key_date = _norm_ws(date_iso or date_text)

        # --- round ---
        round_el = item.select_one(".matches-list__round")
        round_text_raw = _norm(round_el.get_text(" ", strip=True) if round_el else None)
        key_round = _norm_round(round_text_raw)

        # --- teams ---
        team_names = [
            _norm_ws(x.get_text(" ", strip=True))
            for x in item.select(".matches-list__team-names > .matches-list__team-name")
        ]
        team_home = team_names[0] if len(team_names) > 0 else ""
        team_away = team_names[1] if len(team_names) > 1 else ""

        # poskladáme kľúče
        match_key = "|".join([key_date, key_round, team_home, team_away]).strip("|")
        match_key_swapped = "|".join([key_date, key_round, team_away, team_home]).strip("|")

        # fallback bez round (keď sa round líši formátom / chýba)
        match_key_noround = "|".join([key_date, team_home, team_away]).strip("|")
        match_key_noround_swapped = "|".join([key_date, team_away, team_home]).strip("|")

        if not match_key or not key_date:
            continue

        out.append(
            {
                "match_key": match_key,
                "match_key_swapped": match_key_swapped,
                "match_key_noround": match_key_noround,
                "match_key_noround_swapped": match_key_noround_swapped,
                "report_url": report_url,
            }
        )

    return out
