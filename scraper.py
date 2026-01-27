from __future__ import annotations

import argparse
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from config import Config
from storage import Storage
from utils.http_client import HttpClient, RequestLimitExceeded
from utils.robots import RobotsChecker
from parsers.novinky import parse_novinky_list
from parsers.article_type1 import parse_article_type1
from parsers.article_type2 import parse_article_type2
from parsers.zapasy_api import parse_matches_api_json
from parsers.zapasy_reporty import parse_match_reports


def setup_logging(log_dir: Path) -> logging.Logger:
    log_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("hckosice_scraper")
    logger.setLevel(logging.INFO)

    fh = RotatingFileHandler(
        log_dir / "scraper.log",
        maxBytes=2_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    fh.setFormatter(fmt)

    sh = logging.StreamHandler()
    sh.setFormatter(fmt)

    logger.handlers.clear()
    logger.addHandler(fh)
    logger.addHandler(sh)
    return logger


def detect_article_type(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    if soup.select_one("div.match-banner"):
        return "type1"
    if soup.select_one("div.article-news__header-image") or soup.select_one('div[property="schema:text"]'):
        return "type2"
    return "type2"


def fetch_robots_unconditional(url: str, user_agent: str, timeout: int) -> str | None:
    headers = {
        "User-Agent": user_agent,
        "Accept": "text/plain,*/*;q=0.8",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }
    try:
        r = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        if r.status_code == 200:
            txt = (r.text or "").strip()
            return txt or None
        return None
    except Exception:
        return None


def fetch_html_unconditional(url: str, user_agent: str, timeout: int) -> tuple[int, str]:
    headers = {
        "User-Agent": user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }
    r = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
    return r.status_code, (r.text or "")


def _normalize_match_key_for_join(match_key: str) -> str:
    return " ".join((match_key or "").strip().split())


def _build_fallback_key(date_iso: str | None, round_text: str | None, home: str | None, away: str | None) -> str:
    key_date = (date_iso or "").strip()
    key_round = (round_text or "").strip()
    key_home = (home or "").strip()
    key_away = (away or "").strip()
    return "|".join([key_date, key_round, key_home, key_away]).strip("|")


def main() -> int:
    cfg = Config()
    cfg.DATA_DIR.mkdir(parents=True, exist_ok=True)
    logger = setup_logging(cfg.LOG_DIR)

    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="Nevkladá do DB, iba vypíše, čo by uložil.")
    ap.add_argument("--novinky-limit", type=int, default=cfg.NOVINKY_LIMIT)
    ap.add_argument("--max-requests", type=int, default=cfg.MAX_REQUESTS_PER_RUN)
    args = ap.parse_args()

    storage = Storage()
    storage.init_schema()

    http = HttpClient(
        user_agent=cfg.USER_AGENT,
        timeout=cfg.TIMEOUT,
        min_sleep=cfg.MIN_SLEEP,
        max_sleep=cfg.MAX_SLEEP,
        max_retries=cfg.MAX_RETRIES,
        backoff_base=cfg.BACKOFF_BASE,
        backoff_jitter_min=cfg.BACKOFF_JITTER_MIN,
        backoff_jitter_max=cfg.BACKOFF_JITTER_MAX,
        max_requests_per_run=args.max_requests,
        storage_http_meta=storage,
        logger=logger,
    )

    try:
        robots_text = fetch_robots_unconditional(cfg.ROBOTS_URL, cfg.USER_AGENT, int(cfg.TIMEOUT))
        if not robots_text:
            logger.error("robots.txt sa nepodarilo stiahnuť (unconditional) – končím.")
            return 2

        robots = RobotsChecker(cfg.USER_AGENT)
        robots.load(robots_text, cfg.ROBOTS_URL)
        logger.info("robots.txt načítaný a spracovaný (unconditional).")

        # --- NOVINKY ---
        if not robots.can_fetch(cfg.NOVINKY_URL).allowed:
            logger.error(f"Zakázané robots.txt: {cfg.NOVINKY_URL}")
            return 3

        status, novinky_html = fetch_html_unconditional(cfg.NOVINKY_URL, cfg.USER_AGENT, int(cfg.TIMEOUT))
        if status != 200 or not novinky_html.strip():
            logger.warning(f"Novinky list: bez obsahu alebo status={status} – preskakujem.")
        else:
            cards = parse_novinky_list(novinky_html, cfg.BASE_URL, limit=args.novinky_limit)
            logger.info(f"Novinky: našla sa {len(cards)} kariet (limit {args.novinky_limit}).")

            for c in cards:
                url = c["url"]

                rp = robots.can_fetch(url)
                if not rp.allowed:
                    logger.warning(f"Preskakujem (robots): {url}")
                    continue

                detail_res = http.get(url, extra_sleep=True, conditional=True)

                if detail_res.status_code == 304:
                    logger.info(f"Článok nezmenený (304): {url}")
                    continue

                if not detail_res.text:
                    logger.warning(f"Článok bez obsahu: {url}")
                    continue

                atype = detect_article_type(detail_res.text)
                if atype == "type1":
                    parsed = parse_article_type1(detail_res.text, cfg.BASE_URL)
                    parsed_date_text = c.get("date_text")
                    parsed_date_iso = c.get("date_iso")
                else:
                    parsed = parse_article_type2(detail_res.text, cfg.BASE_URL)
                    parsed_date_text = parsed.get("date_text") or c.get("date_text")
                    parsed_date_iso = parsed.get("date_iso") or c.get("date_iso")

                row = {
                    "url": url,
                    "type": parsed["type"],
                    "title": parsed.get("title") or c.get("title"),
                    "date_text": parsed_date_text,
                    "date_iso": parsed_date_iso,
                    "card_image_url": c.get("card_image_url"),
                    "header_image_url": parsed.get("header_image_url"),
                    "match_datetime_text": parsed.get("match_datetime_text"),
                    "match_datetime_iso": parsed.get("match_datetime_iso"),
                    "match_round": parsed.get("match_round"),
                    "match_score": parsed.get("match_score"),
                    "match_is_win": parsed.get("match_is_win"),
                    "match_logo_home_url": parsed.get("match_logo_home_url"),
                    "match_logo_away_url": parsed.get("match_logo_away_url"),
                    "content_html": parsed.get("content_html") or "",
                    "content_text": parsed.get("content_text") or "",
                }

                if args.dry_run:
                    logger.info(f"[DRY-RUN] Uložil by som článok: {row['type']} | {row['title']} | {row['url']}")
                else:
                    inserted, updated = storage.upsert_article(row)
                    if inserted:
                        logger.info(f"INSERT článok: {row['title']} | {row['url']}")
                    elif updated:
                        logger.info(f"UPDATE článok: {row['title']} | {row['url']}")

        # --- ZÁPASY ---
        if not robots.can_fetch(cfg.ZAPASY_URL).allowed:
            logger.error(f"Zakázané robots.txt: {cfg.ZAPASY_URL}")
            return 4

        # HTML (reporty)
        html_res = http.get(cfg.ZAPASY_URL, extra_sleep=False, conditional=False)
        html_text = (html_res.text or "").strip()

        report_items = []
        if html_res.status_code == 200 and html_text:
            report_items = parse_match_reports(html_text, cfg.BASE_URL)
        else:
            logger.warning(f"Zápasy HTML: bez obsahu alebo status={html_res.status_code} – reporty preskakujem.")

        # MAPA reportov – uložíme obe verzie kľúča
        reports_map: dict[str, str] = {}
        for x in report_items or []:
            ru = (x.get("report_url") or "").strip()
            if not ru:
                continue

            mk1 = _normalize_match_key_for_join(x.get("match_key") or "")
            mk2 = _normalize_match_key_for_join(x.get("match_key_swapped") or "")

            if mk1:
                reports_map[mk1] = ru
            if mk2:
                reports_map[mk2] = ru

        logger.info(
            f"Reporty: items={len(report_items) if isinstance(report_items, list) else 0} | "
            f"map={len(reports_map)}"
        )
        if reports_map:
            logger.info(f"Reporty sample keys: {list(reports_map.keys())[:3]}")

        # API
        api_headers = {
            "Accept": "application/json, text/plain, */*",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": cfg.ZAPASY_URL,
            "Origin": cfg.BASE_URL,
        }

        api_res = http.get(
            cfg.ZAPASY_API_URL,
            extra_sleep=False,
            conditional=False,
            extra_headers=api_headers,
        )

        json_text = (api_res.text or "").strip()
        if api_res.status_code != 200 or not json_text:
            logger.warning(f"Zápasy API: bez obsahu alebo status={api_res.status_code} – preskakujem.")
        else:
            matches = parse_matches_api_json(json_text)
            logger.info(f"Zápasy: našlo sa {len(matches)} položiek (API).")

            if matches:
                logger.info(f"API sample keys: {[m.get('match_key') for m in matches[:3]]}")

            matched_reports = 0

            for m in matches:
                mk_api = _normalize_match_key_for_join(m.get("match_key") or "")
                report_url = reports_map.get(mk_api)

                # fallback (ak by niekedy match_key v API parseri nebol rovnaký)
                if not report_url:
                    fallback = _normalize_match_key_for_join(
                        _build_fallback_key(
                            m.get("date_iso"),
                            m.get("round"),
                            m.get("team_home"),
                            m.get("team_away"),
                        )
                    )
                    report_url = reports_map.get(fallback)

                if report_url:
                    matched_reports += 1
                    m["report_url"] = report_url
                else:
                    m["report_url"] = None

                if args.dry_run:
                    logger.info(
                        "[DRY-RUN] zápas: "
                        f"{m.get('status')} | {m.get('team_home')} vs {m.get('team_away')} | "
                        f"{m.get('date_text')} | report={bool(m.get('report_url'))}"
                    )
                else:
                    storage.upsert_match(m)

            logger.info(f"Reporty spárované k zápasom: {matched_reports}/{len(matches)}")

        logger.info(f"Hotovo. Requesty v tomto behu: {http.request_count}")
        return 0

    except RequestLimitExceeded as e:
        logger.error(f"STOP – {e}")
        return 10
    except Exception as e:
        logger.exception(f"Neočakávaná chyba: {e}")
        return 11
    finally:
        storage.close()


if __name__ == "__main__":
    raise SystemExit(main())
