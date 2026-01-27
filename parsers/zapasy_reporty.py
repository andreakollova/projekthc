from __future__ import annotations

from bs4 import BeautifulSoup


def _norm(x: str | None) -> str | None:
    if x is None:
        return None
    s = str(x).strip()
    return s or None


def parse_match_reports(html: str, base_url: str) -> list[dict]:
    """
    Vytiahne report_url z HTML stránky zápasov (tab "Odohrané zápasy").
    Vráti list dictov: {match_key, report_url}

    match_key MUSÍ byť rovnaký ako v zapasy_api.py:
      match_key = "|".join([key_date, key_round, key_home, key_away])

    Kľúče berieme z HTML:
      - key_date: <time class="matches-list__date" datetime="..."> alebo text
      - key_round: .matches-list__round
      - key_home / key_away: .matches-list__team-name (2x)
      - report_url: <a> s textom "Report" (alebo href obsahuje "/zapas")
    """
    soup = BeautifulSoup(html, "lxml")
    out: list[dict] = []

    # v HTML bývajú obe tabu: upcoming aj played, my chceme len tie, kde existuje "Report"
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

        # date_iso
        time_el = item.select_one("time.matches-list__date")
        date_text = time_el.get_text(" ", strip=True) if time_el else None
        date_iso = _norm(time_el.get("datetime")) if time_el else None

        key_date = (date_iso or "").strip() or (date_text or "").strip()

        # round
        round_el = item.select_one(".matches-list__round")
        round_text = _norm(round_el.get_text(" ", strip=True) if round_el else None)

        # teams
        team_names = [
            x.get_text(" ", strip=True)
            for x in item.select(".matches-list__team-names > .matches-list__team-name")
        ]
        team_home = _norm(team_names[0] if len(team_names) > 0 else None)
        team_away = _norm(team_names[1] if len(team_names) > 1 else None)

        key_round = (round_text or "").strip()
        key_home = (team_home or "").strip()
        key_away = (team_away or "").strip()

        match_key = "|".join([key_date, key_round, key_home, key_away]).strip("|")
        if not match_key:
            continue

        out.append(
            {
                "match_key": match_key,
                "report_url": report_url,
            }
        )

    return out
