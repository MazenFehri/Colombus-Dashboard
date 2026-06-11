import html
from datetime import date
from app.services import news_section

PAIRS = [("EUR", "USD"), ("GBP", "USD"), ("USD", "TND"), ("EUR", "TND")]


def _section_html(base: str, quote: str, top, more) -> str:
    rows = []
    for it in top:
        expl = f'<p style="margin:4px 0;color:#cbd5e1">{html.escape(it.explanation)}</p>' if it.explanation else ""
        rows.append(
            f'<li style="margin-bottom:10px">'
            f'<a href="{html.escape(it.url, quote=True)}" style="color:#2DD4BF;text-decoration:none">{html.escape(it.headline)}</a>'
            f'<span style="color:#64748b"> — {html.escape(it.source)}</span>{expl}</li>'
        )
    for it in more:
        rows.append(
            f'<li style="margin-bottom:6px">'
            f'<a href="{html.escape(it.url, quote=True)}" style="color:#94a3b8;text-decoration:none">{html.escape(it.headline)}</a>'
            f'<span style="color:#64748b"> — {html.escape(it.source)}</span></li>'
        )
    body = "".join(rows) or '<li style="color:#64748b">No headlines.</li>'
    return (
        f'<h2 style="color:#2DD4BF;font-size:16px;margin:24px 0 8px">{base}/{quote}</h2>'
        f'<ul style="list-style:none;padding:0;margin:0">{body}</ul>'
    )


def build_digest_html(db, on_date: date) -> tuple[str, str]:
    subject = f"Colombus FX — News digest for {on_date.isoformat()}"
    sections = []
    for base, quote in PAIRS:
        try:
            top, more = news_section.get_pair_news(db, base, quote, on_date)
        except Exception:
            top, more = [], []
        sections.append(_section_html(base, quote, top, more))

    html = (
        '<div style="background:#0F172A;color:#e2e8f0;font-family:Arial,sans-serif;'
        'padding:24px;max-width:640px;margin:0 auto">'
        f'<h1 style="color:#fff;font-size:20px;margin:0">Colombus FX News Digest</h1>'
        f'<p style="color:#94a3b8;margin:4px 0 0">{on_date.isoformat()}</p>'
        + "".join(sections)
        + '<p style="color:#64748b;font-size:12px;margin-top:32px">'
        'You are receiving this because you enabled the daily digest in Colombus. '
        'Educational use only — not financial advice.</p></div>'
    )
    return subject, html
