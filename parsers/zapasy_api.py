from __future__ import annotations

import json
import re

_DIGIT_SCORE_RE = re.compile(r"\d+\s*:\s*\d+")


def _norm_str(x) -> str | None:
    if x is None:
        return None
    s = str(x).strip()
    return s or None


def _to_int_bool(v) -> int | None:
    if v is None:
        return None
    # API používa "0"/"1" ako string
    if isinstance(v, str) and v.strip() in ("0", "1"):
        return 1 if v.strip() == "1" else 0
    try:
        return 1 if bool(int(v)) else 0
    except Exception:
        try:
            return 1 if bool(v) else 0
        except Exception:
            return None


def _is_played_from_status(match_status: str | None) -> bool:
    return (match_status or "").strip().lower() == "played"


def _is_real_score(text: str | None) -> bool:
    if not text:
        return False
    t = text.strip().lower()
    if t == "vs":
        return False
    return bool(_DIGIT_SCORE_RE.search(t))


def parse_matches_api_json(json_text: str) -> list[dict]:
    items = json.loads(json_text)
    if not isinstance(items, list):
        return []

    results: list[dict] = []

    for it in items:
        if not isinstance(it, dict):
            continue

        date_iso = _norm_str(it.get("date"))  # napr. 2025-08-16T15:00:00+0200
        date_text = _norm_str(it.get("dateFormatted"))

        match_status = _norm_str(it.get("matchStatus"))  # played/upcoming
        status = "played" if _is_played_from_status(match_status) else "upcoming"

        round_text = _norm_str(it.get("round"))

        team_home = _norm_str(it.get("homeTeam"))
        team_away = _norm_str(it.get("awayTeam"))

        # venue: z isHome – keď HK Košice je "home"
        # API: isHome "1" => Košice doma, "0" => Košice vonku
        is_home = _to_int_bool(it.get("isHome"))
        venue = "Doma" if is_home == 1 else ("Vonku" if is_home == 0 else None)

        # logá – niekedy bývajú v keys typu homeLogo/awayLogo, necháme robustne
        logo_home_url = _norm_str(it.get("homeLogo") or it.get("homeTeamLogo") or it.get("logoHome"))
        logo_away_url = _norm_str(it.get("awayLogo") or it.get("awayTeamLogo") or it.get("logoAway"))

        score_text = _norm_str(it.get("score") or it.get("result") or it.get("finalScore"))
        score_periods = _norm_str(it.get("scorePeriods") or it.get("periods") or it.get("score_periods"))

        # status override ak je score ale matchStatus chýba / je nespoľahlivé
        if status == "upcoming" and (_is_real_score(score_text) or score_periods):
            status = "played"

        # win – ak API dáva priamo isWin/win
        is_win = None
        if status == "played":
            if "isWin" in it:
                is_win = _to_int_bool(it.get("isWin"))
            elif "win" in it:
                is_win = _to_int_bool(it.get("win"))

        # score uložíme len ak je reálne "X:Y"
        score = score_text if (status == "played" and _is_real_score(score_text)) else None
        score_periods = score_periods if status == "played" else None

        # --- stabilný match_key ---
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
