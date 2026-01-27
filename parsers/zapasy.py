from __future__ import annotations

import re
from bs4 import BeautifulSoup

from utils.dates import parse_datetime_safe

_BG_RE = re.compile(r"url\((['\"]?)(.*?)\1\)")


def _abs_url(base_url: str, src: str) -> str:
    src = (src or "").strip()
    if not src:
        return src
    if src.startswith("http"):
        return src
    if src.startswith("//"):
        return "https:" + src
    if src.startswith("/"):
        return base_url.rstrip("/") + src
    return base_url.rstrip("/") + "/" + src


def _extract_logo_url(base_url: str, node) -> str | None:
    """
    Vytiahne URL loga z:
    - <img src="...">
    - inline style background-image: url(...)
    """
    if not node:
        return None

    img = node.find("img")
    if img and img.get("src"):
        return _abs_url(base_url, img["src"])

    style = node.get("style") or ""
    m = _BG_RE.search(style)
    if m:
        return _abs_url(base_url, m.group(2))

    return None


def _find_logo_node(item, side: str):
    """
    Robustne nájde logo node pre home/away bez spoliehania sa na presnú DOM štruktúru.
    Na webe sa vyskytujú varianty:
      - <div class="matches-list__team-logo matches-list__team-logo--home">...</div>
      - <div class="matches-list__team matches-list__team-logo--away">...</div>
    """
    # 1) priamo element s triedou --home/--away
    node = item.select_one(f".matches-list__team-logo--{side}")
    if node:
        return node

    # 2) niekedy je --home/--away až na vnorenom elemente v .matches-list__team
    node = item.select_one(f".matches-list__team .matches-list__team-logo--{side}")
    if node:
        return node

    return None


def _is_real_score(text: str | None) -> bool:
    """
    Skóre na upcoming kartách býva "VS".
    Odohrané býva napr. "4:3", "2:1 pp", atď.
    """
    if not text:
        return False
    t = text.strip().lower()
    if t == "vs":
        return False
    # aspoň niečo ako 1:0 alebo 10:2
    return bool(re.search(r"\d+\s*:\s*\d+", t))


def parse_matches(html: str, base_url: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    results: list[dict] = []

    for item in soup.select(".matches-list__item"):
        # --- dátum ---
        time_el = item.select_one("time.matches-list__date")
        date_text = time_el.get_text(" ", strip=True) if time_el else None

        if time_el and time_el.get("datetime"):
            date_iso = (time_el.get("datetime") or "").strip() or None
        else:
            # fallback parse z textu
            parsed = parse_datetime_safe(date_text or "")
            date_iso = (parsed or "").strip() or None

        # --- kolo ---
        round_el = item.select_one(".matches-list__round")
        round_text = round_el.get_text(" ", strip=True) if round_el else None

        # --- doma/vonku ---
        venue_el = (
            item.select_one(".matches-list__button.matches-list__button--primary")
            or item.select_one(".matches-list__button")
        )
        venue = venue_el.get_text(" ", strip=True) if venue_el else None

        # --- názvy tímov ---
        team_names = [
            x.get_text(" ", strip=True)
            for x in item.select(".matches-list__team-names > .matches-list__team-name")
        ]
        team_home = team_names[0] if len(team_names) > 0 else None
        team_away = team_names[1] if len(team_names) > 1 else None

        # --- logá ---
        logo_home_node = _find_logo_node(item, "home")
        logo_away_node = _find_logo_node(item, "away")

        logo_home_url = _extract_logo_url(base_url, logo_home_node)
        logo_away_url = _extract_logo_url(base_url, logo_away_node)

        # --- skóre + win/lose ---
        score_el = item.select_one(".matches-list__score")
        raw_score_text = score_el.get_text(" ", strip=True) if score_el else None

        periods_el = item.select_one(".matches-list__score-periods")
        score_periods = periods_el.get_text(" ", strip=True) if periods_el else None

        # status: played/upcoming
        # upcoming môže mať score element, ale text býva "VS"
        status = "played" if _is_real_score(raw_score_text) or score_periods else "upcoming"

        is_win = None
        if score_el and status == "played":
            classes = score_el.get("class", []) or []
            # na webe je často matches-list__score--win
            is_win = 1 if any(c.endswith("__score--win") or c == "matches-list__score--win" for c in classes) else 0

        # score uložíme len ak je reálne "X:Y"
        score = raw_score_text if (status == "played" and _is_real_score(raw_score_text)) else None

        if status == "upcoming":
            score_periods = None

        # --- match_key (stabilný, vhodný pre DB) ---
        # DÔLEŽITÉ: match_key NESMIE obsahovať status, inak vznikajú duplicity (upcoming vs played)
        # Preferujeme ISO datetime, fallback na text
        key_date = (date_iso or "").strip() or (date_text or "").strip()
        key_round = (round_text or "").strip()
        key_home = (team_home or "").strip()
        key_away = (team_away or "").strip()

        match_key = "|".join([key_date, key_round, key_home, key_away]).strip("|")

        results.append(
            {
                "match_key": match_key,
                "status": status,
                "date_text": date_text,
                "date_iso": date_iso,
                "round": round_text,
                "venue": venue,
                "team_home": team_home,
                "team_away": team_away,
                "logo_home_url": logo_home_url,
                "logo_away_url": logo_away_url,
                "score": score,
                "is_win": is_win,
                "score_periods": score_periods,
            }
        )

    return results
