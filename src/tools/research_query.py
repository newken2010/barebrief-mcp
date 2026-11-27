"""research_query: topic -> ranked verbatim excerpts with full citations.

Searches the local corpus of Chinese official sources (cache-first; optional
live refresh). Excerpts are verbatim slices of fetched pages; every finding
carries url + org + fetched_at so the caller can quote and cite safely.
"""
from __future__ import annotations

from typing import Optional

from ..config import get_config
from ..envelope import envelope
from ..sources import research as researchmod


def research_query(query: str, query_zh: str = "", doc_lang: str = "",
                   limit: int = 8, live: bool = False,
                   locale: Optional[str] = None,
                   destination: Optional[str] = None) -> dict:
    """Find sourced passages for a research question.

    query:    free-text terms, any language (e.g. "EV subsidy policy").
    query_zh: Chinese keywords for the ZH corpus (e.g. "新能源汽车 补贴 政策").
              Strongly recommended — the corpus is mostly Chinese.
    doc_lang: filter docs by language: "" (any) | "zh" | "en".
    limit:    max findings (default 8).
    live:     refresh registry homepages first when hits are thin
              (human-paced browser fetch; slower but current).
    locale:   output copy language (en default, zh).

    Returns findings[] with verbatim excerpt + citation per hit. No match and
    nothing reachable -> degraded guidance, never invented content.
    """
    cfg = get_config()
    r = researchmod.research(query, query_zh=query_zh, doc_lang=doc_lang,
                             limit=limit, live=live, cfg=cfg)
    payload = {
        "query": query,
        "query_zh": query_zh,
        "findings": r["findings"],
        "gaps": r["gaps"],
        "corpus_docs": r["corpus_docs"],
        "note": (" excerpts are verbatim source text; cite url + fetched_at"
                 if r["findings"] else
                 " nothing matched — seed the corpus (tools/seed.py) or retry with live=True"),
    }
    return envelope(payload, source=r["source"], data_quality=r["quality"],
                    locale=locale, destination=destination)