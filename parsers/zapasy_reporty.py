from __future__ import annotations

import re
from bs4 import BeautifulSoup

_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")              # YYYY-MM-DD
_TZ_FIX_RE = re.compile(r"([+-]\d{2}):(\d{2})$")         # +01:00 -> +0100


def _norm(x: str | None) -> str | None:
    if x is None:
        return None
    s = str(x).replace("\xa0", " ").strip()              # NBSP -> space
    s = " ".join(s.split())                              # collapse whitespace
    return s or None


def _norm_tz(date_iso: str | None) -> str | None:
    """
    Zjednotí timezone medzi HTML a API:
    - HTML: ...+0100
    - niekedy: ...+01:00
    """
    if not date_iso:
        return None
    s = date_iso.strip()
    s = _TZ_FIX_RE.sub(r"\1\2", s)
    return s


def _date_day_from_any(date_iso_or_text: str | None) -> str | None:
    if not date_iso_or_text:
        return None
    m = _DATE_RE.search(date_iso_or_text)
    return m.group(0) if m else None


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


def _pick_report_anchor(item) -> object | None:
    """
    Na tvojom screenshote je:
      <div class="matches-list__button matches-list__button--secondary">
        <a href="/a-muzstvo/zapasy/...">Report</a>
      </div>

    Preto hľadáme primárne anchor v button--secondary a potom fallback.
    """
    # 1) presne podľa UI "Report" tlačidla
    a = item.select_one(".matches-list__button--secondary a[href]")
    if a:
        return a

    # 2) ak by zmenili triedy, stále nájdeme anchor s textom "Report"
    for a in item.select("a[href]"):
        txt = (_norm(a.get_text(" ", strip=True)) or "").lower()
        if txt == "report" or "report" in txt or "reportáž" in txt or "reportaz" in txt:
            return a

    # 3) posledný fallback: typická URL štruktúra reportov
    for a in item.select("a[href]"):
        href = (a.get("href") or "").strip()
        if "/a-muzstvo/zapasy/" in href:
            return a

    return None


def parse_match_reports(html: str, base_url: str) -> list[dict]:
    """
    Vytiahne report_url z HTML stránky zápasov.

    Vracia list dictov:
      {
        match_key, match_key_swapped,
        join_key, join_key_swapped,
        report_url,
        date_iso, date_day, round, team_1, team_2
      }

    - match_key: FULL datetime + round + teams (keď sa dá)
    - join_key: iba YYYY-MM-DD + round + teams (na najspoľahlivejší join s API)
    - swapped verzie: keby bol v API opačný home/away
    """
    soup = BeautifulSoup(html, "lxml")
    out: list[dict] = []

    # Extra bezpečnosť: ak stránka obsahuje aj upcoming aj played, zoberieme len played tab keď existuje
    scope = soup.select_one("#matches-list-played") or soup

    for item in scope.select(".matches-list__item"):
        report_a = _pick_report_anchor(item)
        if not report_a:
            continue

        report_url = _abs_url(base_url, report_a.get("href") or "")
        if not report_url:
            continue

        # date
        time_el = item.select_one("time.matches-list__date")
        date_text = _norm(time_el.get_text(" ", strip=True) if time_el else None)

        date_iso = None
        if time_el and time_el.get("datetime"):
            date_iso = _norm_tz(_norm(time_el.get("datetime")))
        date_day = _date_day_from_any(date_iso or date_text)

        # round
        round_el = item.select_one(".matches-list__round")
        round_text = _norm(round_el.get_text(" ", strip=True) if round_el else None)

        # teams
        team_names = [
            _norm(x.get_text(" ", strip=True))
            for x in item.select(".matches-list__team-names > .matches-list__team-name")
        ]
        team_1 = team_names[0] if len(team_names) > 0 else None
        team_2 = team_names[1] if len(team_names) > 1 else None

        # key_date_full
        key_date_full = (date_iso or "").strip() or (date_text or "").strip()

        # FULL keys
        mk = "|".join([key_date_full, (round_text or ""), (team_1 or ""), (team_2 or "")]).strip("|")
        mk_swapped = "|".join([key_date_full, (round_text or ""), (team_2 or ""), (team_1 or "")]).strip("|")

        # DAY-only keys (najdôležitejšie na join)
        jk = "|".join([(date_day or ""), (round_text or ""), (team_1 or ""), (team_2 or "")]).strip("|")
        jk_swapped = "|".join([(date_day or ""), (round_text or ""), (team_2 or ""), (team_1 or "")]).strip("|")

        out.append(
            {
                "match_key": mk or None,
                "match_key_swapped": mk_swapped or None,
                "join_key": jk or None,
                "join_key_swapped": jk_swapped or None,
                "report_url": report_url,
                "date_iso": date_iso,
                "date_day": date_day,
                "round": round_text,
                "team_1": team_1,
                "team_2": team_2,
            }
        )

    return out
