from __future__ import annotations

from bs4 import BeautifulSoup

from utils.dates import parse_datetime_safe
from utils.html import extract_img_url_from_node, inner_html, clean_text_from_html

def parse_article_type1(html: str, base_url: str) -> dict:
    soup = BeautifulSoup(html, "lxml")

    title_el = soup.select_one("h1")
    title = title_el.get_text(strip=True) if title_el else None

    banner = soup.select_one("div.match-banner")
    # datetime
    dt_time = banner.select_one(".match-banner__date time[datetime]") if banner else None
    match_datetime_text = dt_time.get_text(" ", strip=True) if dt_time else None
    match_datetime_iso = dt_time.get("datetime") if dt_time and dt_time.get("datetime") else parse_datetime_safe(match_datetime_text or "")

    match_round_el = banner.select_one(".match-banner__round") if banner else None
    match_round = match_round_el.get_text(strip=True) if match_round_el else None

    score_el = banner.select_one(".match-banner__score") if banner else None
    match_score = score_el.get_text(" ", strip=True) if score_el else None
    classes = score_el.get("class", []) if score_el else []
    match_is_win = 1 if any("match-banner__score--win" == c or c.endswith("__score--win") for c in classes) else 0

    logo_home_node = banner.select_one(".match-banner__team-home") if banner else None
    logo_away_node = banner.select_one(".match-banner__team-away") if banner else None
    match_logo_home_url = extract_img_url_from_node(base_url, logo_home_node)
    match_logo_away_url = extract_img_url_from_node(base_url, logo_away_node)

    # text block
    article_block = soup.select_one("div.match-article.block.block--primary") or soup.select_one("div.match-article")
    content_html = inner_html(article_block)
    content_text = clean_text_from_html(content_html)

    return {
        "type": "type1",
        "title": title,
        "header_image_url": None,  # type1 má skôr match banner, nie article-news header
        "match_datetime_text": match_datetime_text,
        "match_datetime_iso": match_datetime_iso,
        "match_round": match_round,
        "match_score": match_score,
        "match_is_win": match_is_win,
        "match_logo_home_url": match_logo_home_url,
        "match_logo_away_url": match_logo_away_url,
        "content_html": content_html,
        "content_text": content_text,
    }
