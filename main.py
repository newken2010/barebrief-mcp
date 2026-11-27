"""FastMCP entrypoint: registers the 4 bilingual research brief tools.

Run:  python main.py            (stdio MCP server)
Test: pytest tests/ -q          (offline; corpus + mocked fetcher)
Seed: python tools/seed.py      (populate corpus from the CN source registry)

Pipeline (question -> sourced bilingual brief skeleton):
  1. research_query    corpus search (cache-first, optional live refresh)
                       -> ranked verbatim excerpts + citations
  2. cite_extract      URL -> canonical citation (title/org/lang/excerpt)
  3. bilingual_brief   findings shaped as {point_cn, citation, en_mirror}
                       for the calling agent to write EN prose over
  4. data_table        numeric rows extracted verbatim, each with citation
                       + as-of date

Compliance-first: public CN official sources only; excerpts are verbatim;
nothing is fabricated — unreachable pages degrade to guidance. Research
support only, never advice.
"""
from fastmcp import FastMCP

from src.config import get_config
from src.tools.bilingual_brief import bilingual_brief as _bilingual_brief
from src.tools.cite_extract import cite_extract as _cite_extract
from src.tools.data_table import data_table as _data_table
from src.tools.research_query import research_query as _research_query

mcp = FastMCP("brief-bilingual-research")


@mcp.tool()
def research_query(query: str, query_zh: str = "", doc_lang: str = "",
                   limit: int = 8, live: bool = False,
                   locale: str | None = None,
                   destination: str | None = None) -> dict:
    """Topic -> ranked verbatim excerpts with citations (CN official sources).

    query: free-text terms, any language. query_zh: Chinese keywords
    (recommended for the ZH corpus). doc_lang: ""|zh|en. limit: max findings.
    live: refresh registry homepages first when hits are thin.
    locale: en (default) | zh.
    """
    return _research_query(query, query_zh, doc_lang, limit, live, locale, destination)


@mcp.tool()
def cite_extract(url: str, live: bool = True, locale: str | None = None,
                 destination: str | None = None) -> dict:
    """URL -> canonical citation (title/org/lang/excerpt/fetched_at).

    url: page to cite. live: fetch when not fresh in cache (default True).
    Unreachable -> degraded with the error; never a guessed citation.
    """
    return _cite_extract(url, live, locale, destination)


@mcp.tool()
def bilingual_brief(query: str, query_zh: str = "", limit: int = 6,
                    live: bool = False, locale: str | None = None,
                    destination: str | None = None) -> dict:
    """Question -> EN/ZH brief skeleton: verbatim CN points + citations.

    Each finding: point_cn (verbatim excerpt), citation{url,title,org,
    fetched_at}, en_mirror (official English page when available).
    The calling agent writes the EN prose over the verbatim points.
    """
    return _bilingual_brief(query, query_zh, limit, live, locale, destination)


@mcp.tool()
def data_table(query: str, query_zh: str = "", limit: int = 10,
               live: bool = False, locale: str | None = None,
               destination: str | None = None) -> dict:
    """Question -> numeric rows extracted verbatim from sourced passages.

    Each row: value + unit + source sentence + citation + as_of (fetch date).
    Never converted or interpolated; no rows -> empty + guidance.
    """
    return _data_table(query, query_zh, limit, live, locale, destination)


def main() -> None:
    _ = get_config()  # fail loud on misconfig
    mcp.run()


if __name__ == "__main__":
    main()