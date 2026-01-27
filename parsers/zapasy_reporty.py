from __future__ import annotations

import unicodedata
from bs4 import BeautifulSoup


def _norm_text(x: str | None) -> str | None:
    if x is None:
        return None
    s = str(x).replace("\xa0", " ").strip()
    s = " ".join(s.split())
    s = unicodedata.normalize("NFKC", s)
    return s or None


def _abs_url(base_url: str, href: str) -> str:
    href = (href or "").strip()
    if href.startswith("http"):
        return href
    if href.startswith("/"):
        return base_url.rstrip("/") + href
    return base_url.rstrip("/") + "/" + href


def parse_match_reports(html: str, base_url: str) -> list[dict]:
    """
    Vytiahne report_url z HTML stránky zápasov.
    Vráti list dictov: {date_iso, date_text, round, team_home, team_away, match_key, match_key_noround, report_url}
    """
    soup = BeautifulSoup(html, "lxml")
    out: list[dict] = []

    # Tip: keď sú tabu, toto zoberie aj played aj upcoming, ale report link filtruje
    for item in soup.select(".matches-list__item"):
        # report link
        report_a = None
        for a in item.select("a[href]"):
            txt = (a.get_text(" ", strip=True) or "").lower()
            href = (a.get("href") or "").strip()
            if not href:
                continue
            if "report" in txt:
                report_a = a
                break

        if not report_a:
            continue

        report_url = _abs_url(base_url, report_a.get("href") or "")
        if not report_url:
            continue

        time_el = item.select_one("time.matches-list__date")
        date_text = _norm_text(time_el.get_text(" ", strip=True) if time_el else None)
        date_iso = _norm_text(time_el.get("datetime") if time_el else None)

        round_el = item.select_one(".matches-list__round")
        round_text = _norm_text(round_el.get_text(" ", strip=True) if round_el else None)

        team_names = [
            _norm_text(x.get_text(" ", strip=True))
            for x in item.select(".matches-list__team-names .matches-list__team-name")
        ]
        team_home = team_names[0] if len(team_names) > 0 else None
        team_away = team_names[1] if len(team_names) > 1 else None

        key_date = (date_iso or date_text or "").strip()
        key_round = (round_text or "").strip()
        key_home = (team_home or "").strip()
        key_away = (team_away or "").strip()

        match_key = "|".join([key_date, key_round, key_home, key_away]).strip("|")
        match_key_noround = "|".join([key_date, key_home, key_away]).strip("|")

        if not key_date or not key_home or not key_away:
            continue

        out.append(
            {
                "date_iso": date_iso,
                "date_text": date_text,
                "round": round_text,
                "team_home": team_home,
                "team_away": team_away,
                "match_key": match_key,
                "match_key_noround": match_key_noround,
                "report_url": report_url,
            }
        )

    return out
