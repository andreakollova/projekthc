from __future__ import annotations

from bs4 import BeautifulSoup


def _norm(x: str | None) -> str | None:
    if x is None:
        return None
    s = str(x).strip()
    return s or None


def _mk(key_date: str, key_round: str, home: str, away: str) -> str:
    return "|".join([key_date, key_round, home, away]).strip("|")


def parse_match_reports(html: str, base_url: str) -> list[dict]:
    """
    Vytiahne report_url z HTML stránky zápasov.
    Vráti list dictov:
      {
        match_key: date|round|home|away,
        match_key_swapped: date|round|away|home,
        report_url: ...
      }

    match_key musí byť kompatibilný so zapasy_api.py kľúčom,
    ale keď HTML poradie tímov nesedí s API, použijeme match_key_swapped.
    """
    soup = BeautifulSoup(html, "lxml")
    out: list[dict] = []

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

        href = (report_a.get("href") or "").strip()
        if not href:
            continue

        if href.startswith("http"):
            report_url = href
        else:
            report_url = base_url.rstrip("/") + (href if href.startswith("/") else "/" + href)

        # date
        time_el = item.select_one("time.matches-list__date")
        date_text = time_el.get_text(" ", strip=True) if time_el else None
        date_iso = _norm(time_el.get("datetime")) if time_el else None
        key_date = (date_iso or "").strip() or (date_text or "").strip()

        # round
        round_el = item.select_one(".matches-list__round")
        round_text = _norm(round_el.get_text(" ", strip=True) if round_el else None)
        key_round = (round_text or "").strip()

        # teams (HTML order)
        team_names = [
            x.get_text(" ", strip=True)
            for x in item.select(".matches-list__team-names > .matches-list__team-name")
        ]
        t1 = _norm(team_names[0] if len(team_names) > 0 else None)
        t2 = _norm(team_names[1] if len(team_names) > 1 else None)

        if not key_date or not key_round or not t1 or not t2:
            continue

        out.append(
            {
                "match_key": _mk(key_date, key_round, t1, t2),
                "match_key_swapped": _mk(key_date, key_round, t2, t1),
                "report_url": report_url,
            }
        )

    return out
