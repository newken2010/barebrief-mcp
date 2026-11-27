# SKILL.md — barebrief (bilingual research brief)

**One-line:** Sourced bilingual (EN+ZH) research briefs over Chinese official
sources — verbatim excerpts, traceable citations, official English mirrors
when they exist. Research support only, never advice.

## What it does

Answers "what do Chinese official sources say about X?" for an English-speaking
agent or analyst, with the hard part guaranteed: every claim is a **verbatim
excerpt** from a fetched official page, every citation carries **url + org +
fetched_at**. The EN prose is yours to write over the verbatim CN points —
that keeps translation traceable instead of invented.

## Tools

1. `research_query(query, query_zh?, doc_lang?, limit?, live?)`
   → ranked findings: `{url, org, title, doc_lang, excerpt, fetched_at, method}`
2. `cite_extract(url, live?)`
   → `{url, title, org, lang, fetched_at, method, excerpt}` — verify before citing
3. `bilingual_brief(query, query_zh?, limit?, live?)`
   → `{findings: [{point_cn (verbatim), citation, en_mirror}], gaps, sources}`
4. `data_table(query, query_zh?, limit?, live?)`
   → `{rows: [{value, unit, context, as_of, on_topic, citation}]}`

## Inputs / outputs (example)

```
research_query(query="China NEV subsidy policy", query_zh="新能源汽车 补贴")
→ dataQuality: public
  findings[0]: {site: gov, doc_lang: mixed, score: 0.75,
                url: https://www.gov.cn/, org: "State Council, PRC",
                excerpt: "…verbatim slice…", fetched_iso: "2026-11-19"}
  gaps: []
```

## Sources (all reachability-verified 2026-11-19, human-paced fetch)

gov.cn (State Council) · miit.gov.cn (MIIT) · stats.gov.cn (NBS) ·
cnipa.gov.cn (CNIPA) · ccgp.gov.cn (MoF procurement) ·
cebpubservice.com (bidding) · english.www.gov.cn (official EN portal —
negotiates by Accept-Language; fetched English-first and offered as
en_mirror only when the stored content verifies as real English,
english_share ≥ 0.5)

## Auth / setup

- No auth. Local SQLite corpus; fetch chain: cache → GhostHand (CDP 9222,
  human-paced) → plain requests.
- Seed once: `python tools/seed.py` (needs Edge/Chrome on 9222 for the
  human-like path; falls back to requests without it).
- MCP client: stdio server, `python main.py` from the project dir.

## Compliance (non-negotiable)

- Research support only — **not advice** (financial/legal included).
- Excerpts are verbatim; numbers are never converted or interpolated;
  every row/finding carries as_of + citation.
- Unreachable/unmatched → `dataQuality: degraded` with the reason. Nothing
  is ever fabricated to fill a gap.
- Public CN official sources only; no login/paywalled content; no
  A-share/market data leaves the local stack.

## Pricing / listing notes (for mcpmarket / dealwork / Fiverr)

- mcpmarket: $9–14 tier ("sourced research briefs, CN official sources").
- dealwork/Fiverr: MCP as the hook; the paid deliverable is the $15–50
  research brief/service order produced with it.
- Differentiator vs generic web-search MCPs: **citations you can verify**
  (url + org + fetch date) and **bilingual CN→EN** coverage of sources
  generic search does not index well.