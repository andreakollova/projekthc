from __future__ import annotations

from bs4 import BeautifulSoup

from utils.dates import parse_datetime_safe
from utils.html import absolutize, extract_img_url_from_node

def parse_novinky_list(html: str, base_url: str, limit: int) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")

    items = []
    for li in soup.select("ul.articles-list > li.article"):
        a = li.select_one("a[href]")
        if not a:
            continue

        url = absolutize(base_url, a.get("href", "").strip())

        title_el = li.select_one(".article__title")
        date_el = li.select_one(".article__date")
        img_wrap = li.select_one(".article__image-wrapper")

        title = title_el.get_text(strip=True) if title_el else None
        date_text = date_el.get_text(strip=True) if date_el else None
        date_iso = parse_datetime_safe(date_text or "") if date_text else None
        card_image_url = extract_img_url_from_node(base_url, img_wrap)

        items.append({
            "url": url,
            "title": title,
            "date_text": date_text,
            "date_iso": date_iso,
            "card_image_url": card_image_url,
        })

        if len(items) >= limit:
            break

    return items
