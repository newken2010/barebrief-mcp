"""cite_extract: URL -> canonical citation record (title/org/lang/excerpt).

The "verify before you cite" tool: fetches a page (cache-first, human-paced
live fallback), stores it in the corpus, and returns a traceable citation.
Unreachable -> degraded with the error, never a guessed citation.
"""
from __future__ import annotations

from typing import Optional

from ..config import get_config
from ..envelope import envelope
from ..sources import fetcher
from ..sources.store import Corpus


def cite_extract(url: str, live: bool = True, locale: Optional[str] = None,
                 destination: Optional[str] = None) -> dict:
    """Extract a verifiable citation from a URL.

    url:  the page to cite (any language; registry sites get org attribution).
    live: fetch when not fresh in cache (default True); False = cache only
          (returns a stale cached doc if present, never fetches).
    Returns citation{url,title,org,lang,fetched_at,method,excerpt} — quote
    from `excerpt` and cite url + fetched_at.
    """
    cfg = get_config()
    corpus = Corpus(cfg.db_path)

    doc = corpus.fresh_url(url, cfg.cache_ttl_sec) if live else corpus.get(url)
    via = "corpus_cache"
    if doc is None:
        if not live:
            return envelope(
                {"url": url, "citation": None,
                 "note": "not in corpus and live=False (cache-only)"},
                source="corpus_cache", data_quality="degraded",
                locale=locale, destination=destination)
        rec = fetcher.fetch(url, cfg)
        if not rec.get("ok") or not rec.get("text"):
            return envelope(
                {"url": url, "citation": None,
                 "note": f"unreachable: {rec.get('err', 'empty body')}"},
                source="degraded", data_quality="degraded",
                locale=locale, destination=destination)
        doc = fetcher.doc_from_fetch(rec)
        corpus.upsert(doc)
        via = rec.get("method", "live")

    citation = {
        "url": doc["url"], "title": doc["title"], "org": doc["org"],
        "lang": doc["lang"], "fetched_at": doc["fetched_at"],
        "method": doc["method"], "excerpt": (doc["text"] or "")[:400],
    }
    return envelope({"url": url, "citation": citation, "note": ""},
                    source=via,
                    data_quality="live" if via.endswith("_live") else "public",
                    locale=locale, destination=destination)