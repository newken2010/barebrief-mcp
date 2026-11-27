"""data_table: question -> numeric rows pulled verbatim from sourced passages.

Every row carries the sentence it came from + the citation, and an as-of date
(doc fetched_at). Values are never interpolated or converted — if the source
says 亿元, the row says 亿元. No match -> empty rows + guidance (degraded).
"""
from __future__ import annotations

import re
from typing import Optional

from ..config import get_config
from ..envelope import envelope
from ..sources import research as researchmod
from ..sources.store import Corpus, _terms

# number + unit (CN and EN), e.g. 12.5% / 3.2亿元 / 1500万辆 / $4.2
# multi-char units MUST precede their single-char prefixes (万辆 before 万)
# NOTE: "$4.2B" does NOT match — B/billion is not a unit here (too ambiguous);
# bare "$4.2" does. Keep examples honest with the pattern.
_NUM = r"\d[\d,]*(?:\.\d+)?"
_UNIT = (r"%|％|个百分点|基点|万千瓦时|平方公里|万平方米|千瓦时|"
         "万亿元|亿元|万元|万辆|万件|万台|万吨|亿美元|美元|万亿美元|"
         r"美金|英镑|欧元|日元|RMB|USD|EUR|GBP|JPY|CNY|"
         r"亿|万|件|台|辆|人|吨|元|公里|平方米|\$|€|£|¥")
_ROW = re.compile(rf"(?P<value>{_NUM})\s*(?P<unit>{_UNIT})")
_SENT = re.compile(r"[。！？；!?;\n\r]+")


def _rows_from(text: str, terms: list, citation: dict, as_of: str) -> list:
    """Extract number+unit rows from a query-matched doc.

    Relevance is at DOC level (the doc already matched the query); each row
    carries on_topic=True when its own sentence mentions a query term, so the
    caller can rank. Contexts are clean sentences (split on CJK/ASCII
    punctuation and newlines — homepage snapshots are newline-heavy).
    Verbatim, always cited.
    """
    rows, seen = [], set()
    tl = [t.lower() for t in terms if t]
    sents, pos = [], 0
    for m in _SENT.finditer(text):
        sents.append(text[pos:m.end()])
        pos = m.end()
    sents.append(text[pos:])
    for s in sents:
        s = s.strip()
        if not s:
            continue
        low = s.lower()
        on_topic = any(t in low for t in tl) if tl else False
        for m in _ROW.finditer(s):
            key = (m.group("value"), m.group("unit"), s[:40])
            if key in seen:
                continue
            seen.add(key)
            rows.append({"value": m.group("value"), "unit": m.group("unit"),
                         "context": s[:200], "as_of": as_of, "on_topic": on_topic,
                         "citation": citation})
    rows.sort(key=lambda r: not r["on_topic"])
    return rows


def data_table(query: str, query_zh: str = "", limit: int = 10,
               live: bool = False, locale: Optional[str] = None,
               destination: Optional[str] = None) -> dict:
    """Extract cited numeric rows relevant to a research question.

    query / query_zh / live: same meaning as research_query.
    limit: max rows (default 10).

    Rows are verbatim extractions: value + unit + the source sentence +
    citation + as-of (page fetch date) + on_topic (sentence mentions a query
    term; on-topic rows sort first). Never converted, never interpolated.
    """
    cfg = get_config()
    r = researchmod.research(query, query_zh=query_zh, limit=max(limit, 6),
                             live=live, cfg=cfg)
    corpus = Corpus(cfg.db_path)
    terms = list(dict.fromkeys(_terms(query_zh) + _terms(query)))

    rows = []
    for f in r["findings"]:
        doc = corpus.get(f["url"]) or {"text": f["excerpt"]}
        citation = {"url": f["url"], "title": f["title"], "org": f["org"],
                    "fetched_at": f["fetched_at"]}
        rows.extend(_rows_from(doc.get("text", ""), terms, citation, f["fetched_iso"]))
        if len(rows) >= limit:
            break
    rows = rows[:limit]

    payload = {
        "query": query,
        "query_zh": query_zh,
        "rows": rows,
        "gaps": r["gaps"] + ([] if rows else ["no numeric rows in matched passages"]),
        "note": (" values are verbatim from the cited sentence; as_of = page "
                  "fetch date; on_topic rows mention a query term (sorted "
                  "first); verify against the original before use"),
    }
    quality = r["quality"] if rows else (
        "partial" if r["findings"] else "degraded")
    return envelope(payload, source=r["source"], data_quality=quality,
                    locale=locale, destination=destination)