"""Shared retrieval logic for the research tools: corpus search with optional
live refresh of the registry, provenance-aware quality marking.

Quality contract (mirrors envelope.py):
  - every finding carries url/title/org/fetched_at/method -> traceable
  - "public"  = answered entirely from cache (fetched before this call)
  - "live"    = at least one doc fetched during this call
  - "partial" = real hits with a known hole (e.g. EN query only matched ZH
                docs; caller should pass ZH keywords)
  - "degraded"= nothing matched and nothing reachable; guidance, not data
"""
from __future__ import annotations

import time

from ..config import SourceConfig, get_config
from ..sources import fetcher, registry
from ..sources.store import Corpus  # noqa: F401  (re-exported for tools/tests)


_LANG_GROUP = {"en": ("en", "mixed"), "zh": ("zh", "mixed"), "": ()}


def refresh_registry(cfg: SourceConfig) -> tuple[list, list]:
    """Fetch every registry URL (homes + EN mirrors) into the corpus.

    Returns (docs_written, errors). Human-paced when GhostHand answers;
    each site is independent — one failure never blocks the others.
    """
    corpus = Corpus(cfg.db_path)
    docs, errors = [], []
    for src in registry.SOURCES:
        for url in (src["home"], src.get("en") or ""):
            if not url:
                continue
            fresh = corpus.fresh_url(url, cfg.cache_ttl_sec)
            if fresh:
                docs.append(fresh)
                continue
            rec = fetcher.fetch(url, cfg)
            if rec.get("ok") and rec.get("text"):
                doc = fetcher.doc_from_fetch(rec)
                corpus.upsert(doc)
                docs.append(doc)
            else:
                errors.append({"url": url, "err": rec.get("err", "empty body")})
    return docs, errors


def research(query: str, query_zh: str = "", doc_lang: str = "", limit: int = 8,
             live: bool = False, cfg: SourceConfig | None = None) -> dict:
    """Search the corpus (optionally refreshing it live first).

    query:     free-text terms in any language
    query_zh:  Chinese keywords — strongly recommended for the ZH corpus
    doc_lang:  filter returned docs by language ("" = any, "zh", "en")
    live:      refresh registry homepages before searching when hits are thin
    """
    cfg = cfg or get_config()
    corpus = Corpus(cfg.db_path)
    before = {d["url"]: d["fetched_at"] for d in corpus.all_docs()}

    fetched_now = False
    refresh_errors: list = []
    if live:
        _docs, refresh_errors = refresh_registry(cfg)
        after = {d["url"]: d["fetched_at"] for d in corpus.all_docs()}
        fetched_now = any(after.get(u, 0) > ts for u, ts in before.items()) or bool(
            set(after) - set(before))

    # merge searches: query terms + ZH terms (dedupe by url, keep best score)
    langs = _LANG_GROUP.get(doc_lang, ())
    hits: dict[str, dict] = {}
    for terms in filter(None, (query_zh, query)):
        for h in corpus.search(terms, limit=max(limit * 2, 16), langs=langs):
            url = h["url"]
            if url not in hits or h["score"] > hits[url]["score"]:
                hits[url] = h
    ranked = sorted(hits.values(), key=lambda h: (-h["score"], -h["fetched_at"]))[:limit]

    findings = [{
        "url": h["url"], "site": h["site"], "org": h["org"], "title": h["title"],
        "doc_lang": h["lang"], "excerpt": h["excerpt"], "score": h["score"],
        "fetched_at": h["fetched_at"], "fetched_iso": _iso(h["fetched_at"]),
        "method": h["method"],
    } for h in ranked]

    live_findings = [f for f in findings if f["fetched_at"] > before.get(f["url"], 0)]
    if findings and live_findings:
        quality, source = "live", "ghosthand_live" if any(
            f["method"] == "ghosthand_live" for f in live_findings) else "requests_live"
    elif findings:
        quality, source = "public", "corpus_cache"
    else:
        quality, source = "degraded", "corpus_cache"

    gaps: list[str] = []
    if not findings:
        gaps.append("no corpus match — run the seed (tools/seed.py) or retry with live=True")
    elif doc_lang == "en" and all(f["doc_lang"] == "zh" for f in findings):
        pass  # caller explicitly asked EN; empty result handled above
    elif not query_zh and any(f["doc_lang"] == "zh" for f in findings):
        gaps.append("ZH corpus matched on raw query terms only — pass query_zh "
                    "(Chinese keywords) for much better recall")
    if refresh_errors:
        gaps.append(f"live refresh partial: {len(refresh_errors)} source(s) unreachable")

    return {"findings": findings, "quality": quality, "source": source,
            "gaps": gaps, "fetched_now": fetched_now,
            "corpus_docs": corpus.count()}


def _iso(ts: int) -> str:
    if not ts:
        return ""
    return time.strftime("%Y-%m-%d", time.localtime(ts))


def en_mirror_for(site_key: str, cfg: SourceConfig | None = None) -> str | None:
    """Return the EN mirror URL for a site if the corpus PROVES it is English.

    Two conditions, both content-based (2026-11-19 audit lesson — a ZH-locale
    fetch of english.www.gov.cn returns a Chinese body with an English nav,
    which used to slip through as "mixed = English-usable"):
      1. the mirror doc exists and is not predominantly Chinese;
      2. english_share(text) >= 0.5 — most lines are real English.
    """
    cfg = cfg or get_config()
    src = registry.by_key(site_key)
    if not src or not src.get("en"):
        return None
    doc = Corpus(cfg.db_path).get(src["en"])
    if not doc or doc.get("lang") not in ("en", "mixed"):
        return None
    if fetcher.english_share(doc.get("text", "")) < 0.5:
        return None
    return src["en"]