from __future__ import annotations

from bs4 import BeautifulSoup


def parse_match_report_detail(html: str, base_url: str) -> dict:
    soup = BeautifulSoup(html, "lxml")

    title_el = (
        soup.select_one("h1")
        or soup.select_one(".article__title")
        or soup.select_one(".page-title")
    )
    title = title_el.get_text(" ", strip=True) if title_el else None

    content_root = (
        soup.select_one("div.match-article")
        or soup.select_one('div[property="schema:text"]')
        or soup.select_one(".article-news__content")
        or soup.select_one("main")
    )

    content_html = ""
    content_text = ""

    if content_root:
        for bad in content_root.select(
            "script, style, noscript, .addtoany-sharebar, .share, .social"
        ):
            bad.decompose()

        content_html = str(content_root)
        content_text = content_root.get_text("\n", strip=True)

    return {
        "type": "match_report",
        "title": title,
        "content_html": content_html,
        "content_text": content_text,
        "header_image_url": None,
    }
