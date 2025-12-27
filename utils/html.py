import re
from bs4 import BeautifulSoup

_BG_RE = re.compile(r"background-image\s*:\s*url\((['\"]?)(.*?)\1\)", re.IGNORECASE)

def absolutize(base_url: str, maybe_relative: str) -> str:
    if not maybe_relative:
        return maybe_relative
    if maybe_relative.startswith("http://") or maybe_relative.startswith("https://"):
        return maybe_relative
    if maybe_relative.startswith("//"):
        return "https:" + maybe_relative
    if maybe_relative.startswith("/"):
        return base_url.rstrip("/") + maybe_relative
    return base_url.rstrip("/") + "/" + maybe_relative

def extract_img_url_from_node(base_url: str, node) -> str | None:
    """
    Skúsi nájsť img src, inak background-image v style atribúte.
    """
    if not node:
        return None

    img = node.find("img")
    if img and img.get("src"):
        return absolutize(base_url, img["src"])

    style = node.get("style") or ""
    m = _BG_RE.search(style)
    if m:
        return absolutize(base_url, m.group(2))

    return None

def inner_html(node) -> str:
    if not node:
        return ""
    return "".join(str(x) for x in node.contents)

def clean_text_from_html(html: str) -> str:
    soup = BeautifulSoup(html or "", "lxml")
    text = soup.get_text("\n", strip=True)
    # jemné upratanie prázdnych riadkov
    lines = [ln.strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln]
    return "\n".join(lines)
