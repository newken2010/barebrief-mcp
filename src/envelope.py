"""Shared response envelope + data-quality markers (bilingual research brief MCP).

Every tool returns a dict with:
  - data:        the payload (findings / citation / brief skeleton / table rows)
  - source:      which path answered (corpus_cache / ghosthand_live /
                 requests_live / mixed / degraded)
  - dataQuality: "live" | "public" | "partial" | "draft" | "degraded"
      * live     -> a page fetched during this call (ghosthand or requests)
      * public   -> answered from the local corpus cache (fetched earlier,
                    provenance recorded per doc: url + fetched_at + method)
      * partial  -> real results with known holes (e.g. only ZH matched an
                    EN query; gaps are listed, never papered over)
      * draft    -> never used by this MCP: we do not generate unverified text
      * degraded -> nothing matched / nothing reachable; guidance, not data
  - disclaimer:  compliance note (always present; research-only, not advice)
  - locale:      output language code ("en" default, "zh" supported)

Excerpts are verbatim slices of fetched pages; citations carry url + title +
org + fetched_at so every claim is traceable. EN delivery is the caller's
prose; this MCP guarantees the CN source text and the citation, nothing else.
"""
from __future__ import annotations

from typing import Any

SUPPORTED = ("en", "zh")
_DEFAULT = "en"

RESEARCH_EN = (
    "Research support only: cited public sources, verbatim excerpts, not "
    "advice. Verify figures against the original pages before any decision."
)
RESEARCH_ZH = (
    "仅供研究参考：引文均来自公开来源、摘录为原文切片，不构成任何建议。"
    "决策前请核对原始页面。"
)


def normalize_locale(locale: str | None, destination: str | None = None) -> str:
    """Explicit `locale` wins (en/zh); else infer from `destination`; else EN."""
    if locale:
        loc = locale.strip().lower()
        if loc in SUPPORTED:
            return loc
        base = loc.split("-")[0].split("_")[0]
        if base in SUPPORTED:
            return base
    if destination:
        dest = destination.strip().upper()
        if dest in ("CN", "TW", "HK", "MO", "SG"):
            return "zh"
    return _DEFAULT


def localize(text: str, locale: str) -> str:
    if locale == "zh" and text == RESEARCH_EN:
        return RESEARCH_ZH
    return text


def envelope(data: Any, source: str, data_quality: str, disclaimer: str = "",
             locale: str | None = None, destination: str | None = None) -> dict:
    out_locale = normalize_locale(locale, destination)
    text = disclaimer or RESEARCH_EN
    return {
        "data": data,
        "source": source,
        "dataQuality": data_quality,
        "disclaimer": localize(text, out_locale),
        "locale": out_locale,
    }