from __future__ import annotations

from bs4 import BeautifulSoup

from utils.dates import normalize_added_date
from utils.html import extract_img_url_from_node, inner_html, clean_text_from_html

def parse_article_type2(html: str, base_url: str) -> dict:
    soup = BeautifulSoup(html, "lxml")

    title_el = soup.select_one(".article-news h1") or soup.select_one("h1")
    title = title_el.get_text(strip=True) if title_el else None

    info_el = soup.select_one(".article-news__info")
    date_text = info_el.get_text(" ", strip=True) if info_el else None
    date_iso = normalize_added_date(date_text or "") if date_text else None

    header = soup.select_one("div.article-news__header-image")
    header_image_url = extract_img_url_from_node(base_url, header)

    body = soup.select_one('div[property="schema:text"]') or soup.select_one(".article-news main div[property]")
    content_html = inner_html(body)
    content_text = clean_text_from_html(content_html)

    return {
        "type": "type2",
        "title": title,
        "date_text": date_text,
        "date_iso": date_iso,
        "header_image_url": header_image_url,
        "match_datetime_text": None,
        "match_datetime_iso": None,
        "match_round": None,
        "match_score": None,
        "match_is_win": None,
        "match_logo_home_url": None,
        "match_logo_away_url": None,
        "content_html": content_html,
        "content_text": content_text,
    }
