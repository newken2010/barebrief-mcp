"""Registry of Chinese official sources for bilingual research briefs.

Every entry's `home` was reachability-tested on 2026-11-19 via GhostHand
(human-paced CDP fetch; 6/6 OK with real body text). The gov.cn `en` mirror
(linked from gov.cn's own EN menu item) negotiates by Accept-Language:
English headers -> real English (english_share 0.999, verified), Chinese
headers -> Chinese body. The fetcher therefore fetches EN mirrors with
English headers (requests-first) and verifies english_share >= 0.5 before
the doc may serve as an en_mirror. No search-URL patterns are invented:
the corpus holds homepages + whatever cite_extract verifies on demand.
"""
from __future__ import annotations

SOURCES = [
    {
        "key": "gov",
        "name": "中国政府网",
        "org": "State Council, PRC",
        "home": "https://www.gov.cn/",
        "en": "https://english.www.gov.cn/",
        "lang": "zh",
    },
    {
        "key": "miit",
        "name": "工业和信息化部",
        "org": "MIIT",
        "home": "https://www.miit.gov.cn/",
        "en": "",
        "lang": "zh",
    },
    {
        "key": "stats",
        "name": "国家统计局",
        "org": "National Bureau of Statistics",
        "home": "https://www.stats.gov.cn/",
        "en": "",
        "lang": "zh",
    },
    {
        "key": "cnipa",
        "name": "国家知识产权局",
        "org": "CNIPA",
        "home": "https://www.cnipa.gov.cn/",
        "en": "",
        "lang": "zh",
    },
    {
        "key": "ccgp",
        "name": "中国政府采购网",
        "org": "Ministry of Finance (CCGP)",
        "home": "https://www.ccgp.gov.cn/",
        "en": "",
        "lang": "zh",
    },
    {
        "key": "cebpub",
        "name": "中国招标投标公共服务平台",
        "org": "CEB Public Service",
        "home": "https://www.cebpubservice.com/",
        "en": "",
        "lang": "zh",
    },
]


def by_key(key: str) -> dict | None:
    for s in SOURCES:
        if s["key"] == key:
            return s
    return None


def by_url(url: str) -> dict | None:
    """Match a doc URL back to its registry entry (for org attribution)."""
    for s in SOURCES:
        for u in (s["home"], s["en"]):
            if u and (url == u or url.startswith(u.rstrip("/") + "/")
                      or _same_host(url, u)):
                return s
    return None


def _same_host(a: str, b: str) -> bool:
    try:
        from urllib.parse import urlparse
        ha, hb = urlparse(a).netloc.lower(), urlparse(b).netloc.lower()
        return bool(ha) and ha == hb
    except Exception:
        return False