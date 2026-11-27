"""bilingual_brief: question -> EN/ZH aligned brief skeleton with citations.

The MCP guarantees the hard part — verbatim CN source text + traceable
citations + EN mirror links where they exist. The EN prose is the calling
agent's job (translation of a verbatim excerpt stays traceable; invented
prose would not be). Output shape:

  {question, question_zh,
   findings: [{point_cn (verbatim), citation{...}, en_mirror|null}],
   gaps: [...], sources: [...]}
"""
from __future__ import annotations

from typing import Optional

from ..config import get_config
from ..envelope import envelope
from ..sources import research as researchmod


def bilingual_brief(query: str, query_zh: str = "", limit: int = 6,
                    live: bool = False, locale: Optional[str] = None,
                    destination: Optional[str] = None) -> dict:
    """Build a sourced bilingual brief skeleton for a research question.

    query:    the question, any language.
    query_zh: Chinese keywords (recommended for recall on the ZH corpus).
    limit:    max findings (default 6).
    live:     refresh registry homepages first when hits are thin.

    Each finding: point_cn = verbatim excerpt (quote it, don't paraphrase
    silently), citation = {url,title,org,fetched_at}, en_mirror = official
    English page when the site has one and it is in the corpus.
    """
    cfg = get_config()
    r = researchmod.research(query, query_zh=query_zh, limit=limit, live=live, cfg=cfg)

    findings = []
    for f in r["findings"]:
        findings.append({
            "point_cn": f["excerpt"],
            "citation": {"url": f["url"], "title": f["title"], "org": f["org"],
                         "fetched_at": f["fetched_at"], "fetched_iso": f["fetched_iso"]},
            "en_mirror": researchmod.en_mirror_for(f["site"], cfg) if f["site"] else None,
            "doc_lang": f["doc_lang"],
        })

    gaps = list(r["gaps"])
    if findings and not query_zh:
        gaps.append("pass query_zh (Chinese keywords) to improve ZH recall")
    if not findings:
        gaps.append("no sourced findings — seed the corpus or retry with live=True")

    payload = {
        "question": query,
        "question_zh": query_zh,
        "findings": findings,
        "gaps": gaps,
        "sources": sorted({f["citation"]["url"] for f in findings}),
        "how_to_use": ("quote point_cn verbatim with its citation; write the EN "
                       "prose yourself; use en_mirror when present"),
    }
    return envelope(payload, source=r["source"], data_quality=r["quality"],
                    locale=locale, destination=destination)