"""Page fetcher with provenance and locale correctness.

Routing: ZH homepages -> GhostHand (human-paced CDP) first, requests
fallback; EN mirrors -> requests first (Accept-Language negotiation is what
actually gets English out of the gov EN portal). Every fetch records how it
happened (method) so the corpus stays auditable, EN-mirror fetches are
verified to be actually English, and a failed fetch is a failed fetch —
nothing is fabricated.
"""
from __future__ import annotations

import re
import time
from html.parser import HTMLParser

import requests

from ..config import SourceConfig
from ..sources import registry

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

_SKIP = re.compile(r"\s+")


class _Text(HTMLParser):
    """Minimal readable-text extractor (script/style dropped)."""

    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self._skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript") and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip and data and data.strip():
            self.parts.append(data.strip())

    def text(self) -> str:
        return _SKIP.sub(" ", " ".join(self.parts)).strip()


_CJK = re.compile(r"[\u4e00-\u9fff]")
_LATIN = re.compile(r"[A-Za-z]")

AL_ZH = "zh-CN,zh;q=0.9,en;q=0.8"
AL_EN = "en-US,en;q=0.9"


def accept_language_for(url: str) -> str:
    """Locale-correct Accept-Language for a URL.

    Measured 2026-11-19: english.www.gov.cn serves REAL ENGLISH with an
    English Accept-Language (cjk_ratio 0.00) and CHINESE with a Chinese one
    (cjk_ratio 0.38) — same URL, content negotiated by request header. So the
    registry's `en` mirrors must be fetched English-first, homes ZH-first.
    A hardcoded ZH-first header silently poisons the "bilingual" corpus.
    """
    src = registry.by_url(url)
    if src and src.get("en") and url.startswith(src["en"]):
        return AL_EN
    return AL_ZH


def detect_lang(text: str) -> str:
    """Content-based language detection (URL is not trusted).

    Thresholds: cjk_ratio >0.6 zh, <0.15 en, else mixed. Note: `mixed` is NOT
    proof of English usability — a Chinese page with an English nav is also
    "mixed". Use `english_share` to verify actual English content.
    """
    if not text:
        return ""
    ratio = len(_CJK.findall(text)) / max(len(text), 1)
    if ratio > 0.6:
        return "zh"
    if ratio < 0.15:
        return "en"
    return "mixed"


def english_share(text: str) -> float:
    """Character-weighted English share of a page (letters only).

    The honest test for "is this page actually English": english.www.gov.cn
    with English headers -> ~1.0; the same URL with Chinese headers (Chinese
    body, English nav) -> well under 0.5. Character-weighted (not per-line)
    so a short English nav cannot outvote a long Chinese body.
    """
    text = text or ""
    latin = len(_LATIN.findall(text))
    cjk = len(_CJK.findall(text))
    if latin + cjk == 0:
        return 0.0
    return latin / (latin + cjk)


def html_to_text(html: str) -> str:
    p = _Text()
    try:
        p.feed(html)
    except Exception:
        pass
    return p.text()


def _title_of(html: str) -> str:
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
    return _SKIP.sub(" ", m.group(1)).strip() if m else ""


def fetch_via_requests(url: str, cfg: SourceConfig,
                       accept_language: str = "") -> dict:
    al = accept_language or accept_language_for(url)
    r = requests.get(url, headers={"User-Agent": _UA, "Accept-Language": al},
                     timeout=cfg.request_timeout)
    r.encoding = r.apparent_encoding or r.encoding
    return {"ok": r.status_code == 200, "url": url, "status": r.status_code,
            "title": _title_of(r.text), "text": html_to_text(r.text),
            "method": "requests_live", "fetched_at": int(time.time())}


def fetch_via_ghosthand(url: str, cfg: SourceConfig,
                        accept_language: str = "") -> dict:
    """Human-paced fetch through the real browser (GhostHand over CDP).

    Attaches a new tab (never hijacks the user's tab), navigates with human
    rhythm, reads title + body text, closes the tab. Requires Edge/Chrome
    running with --remote-debugging-port=<cfg.cdp_port>.

    Two correctness guards learned the hard way (2026-11-19):
    - goto() resolves on 404 too — the HTTP status is checked, a >=400 page
      is a failed fetch, never stored as content;
    - a CDP acceptLanguage override is attempted for EN mirrors but was
      MEASURED not to take effect on the gov EN portal (ZH-locale browser
      still got the Chinese body) — `fetch()` therefore routes EN mirrors to
      requests first and verifies english_share after every attempt.
    """
    import sys
    from pathlib import Path
    try:
        from ghosthand import GhostDriver  # pip-installed (preferred)
    except ImportError:
        # sibling layout: <workspace>/ghosthand next to <workspace>/mcp-*/
        sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "ghosthand"))
        from ghosthand import GhostDriver  # noqa: E402

    al = accept_language or accept_language_for(url)
    d = GhostDriver(pace="normal", seed=2026)
    try:
        pg = d.attach(new_tab=True)
        # locale override BEFORE navigation so the first response is localized
        try:
            cdp = pg.context.new_cdp_session(pg)
            cdp.send("Network.setUserAgentOverride",
                     {"userAgent": _UA, "acceptLanguage": al})
        except Exception:
            pass  # override is best-effort; requests fallback covers the rest
        resp = pg.goto(url, wait_until="domcontentloaded", timeout=35000)
        status = getattr(resp, "status", 0) or 0
        if status >= 400:
            return {"ok": False, "url": url, "status": status,
                    "err": f"ghosthand: HTTP {status}"}
        pg.wait_for_timeout(2500)
        info = pg.evaluate("""() => ({
            title: document.title || '',
            text: document.body ? document.body.innerText : ''
        })""")
        return {"ok": True, "url": pg.url, "status": status or 200,
                "title": (info.get("title") or "")[:200],
                "text": (info.get("text") or "")[:cfg.max_text_chars],
                "method": "ghosthand_live", "fetched_at": int(time.time())}
    finally:
        try:
            d.close()
        except Exception:
            pass


def fetch(url: str, cfg: SourceConfig, method: str = "auto") -> dict:
    """Fetch one page. `method`: auto | ghosthand | requests.

    Routing (learned 2026-11-19, the hard way):
    - ZH homepages: GhostHand first (human-like, passes walls), requests
      fallback.
    - EN mirrors: requests FIRST — header locale negotiation is proven to
      return real English there, while a ZH-locale browser (even with a CDP
      acceptLanguage override, which was measured NOT to take effect on the
      gov EN portal) serves the Chinese body.
    Either way an EN-mirror fetch is verified after the fact: if the content
    is not actually English (english_share < 0.5) the next method is tried,
    so a poisoned doc never enters the corpus.
    """
    al = accept_language_for(url)
    en_url = al == AL_EN
    if method == "auto":
        order = ["requests", "ghosthand"] if en_url else ["ghosthand", "requests"]
    else:
        order = [method] + [m for m in ("ghosthand", "requests") if m != method]

    last = None
    for m in order:
        if m == "ghosthand" and not cfg.ghosthand_enabled:
            continue
        if m == "requests" and not cfg.requests_enabled:
            continue
        try:
            rec = (fetch_via_ghosthand(url, cfg, al) if m == "ghosthand"
                   else fetch_via_requests(url, cfg, al))
        except Exception as e:
            last = {"ok": False, "url": url, "err": f"{m}: {type(e).__name__}: {e}"}
            continue
        if not rec.get("ok") or not rec.get("text"):
            last = rec
            continue
        if en_url:
            share = english_share(rec["text"])
            if share < 0.5:
                last = {"ok": False, "url": url,
                        "err": f"{m}: EN mirror returned non-English content "
                               f"(english_share {share:.2f})"}
                continue
        return rec
    return last or {"ok": False, "url": url, "err": "no fetch method enabled"}


def doc_from_fetch(rec: dict) -> dict:
    """Turn a fetch record into a corpus doc (org attributed from registry).

    Language comes from the fetched CONTENT, not the URL — and the content
    depends on the request locale (see accept_language_for), which the fetch
    layer already got right for registry URLs.
    """
    src = registry.by_url(rec.get("url", ""))
    lang = detect_lang(rec.get("text", ""))
    return {
        "url": rec.get("url", ""),
        "site": src["key"] if src else "",
        "org": src["org"] if src else "",
        "lang": lang,
        "title": rec.get("title", ""),
        "method": rec.get("method", ""),
        "fetched_at": rec.get("fetched_at", int(time.time())),
        "text": rec.get("text", ""),
    }