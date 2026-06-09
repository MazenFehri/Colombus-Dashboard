import httpx
from lxml import html as lxml_html

MAX_CHARS = 3000
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ColombusFX/1.0)"}


def fetch_article_text(url: str) -> str | None:
    """Download an article page and return its main body text, or None on any failure.

    Best-effort extraction: concatenates <p> text, trims boilerplate-ish short
    fragments, and caps length. Never raises.
    """
    try:
        resp = httpx.get(url, headers=_HEADERS, timeout=8, follow_redirects=True)
    except Exception:
        return None
    if resp.status_code != 200 or not resp.text:
        return None
    try:
        tree = lxml_html.fromstring(resp.text)
    except Exception:
        return None

    paragraphs: list[str] = []
    for p in tree.xpath("//p"):
        text = " ".join(p.text_content().split()).strip()
        if len(text) >= 40:  # skip nav/boilerplate fragments
            paragraphs.append(text)

    body = " ".join(paragraphs).strip()
    if not body:
        return None
    return body[:MAX_CHARS]
