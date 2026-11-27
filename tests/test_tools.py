import json
import time

import pytest

import src.config as config
from src.config import SourceConfig
from src.sources.store import Corpus
from src.tools import bilingual_brief, cite_extract, data_table, research_query

GOV_TEXT = (
    "国务院印发关于推动新能源汽车产业高质量发展的若干意见。"
    "2025年中央财政安排新能源汽车补贴资金120亿元，支持充换电基础设施建设。"
    "各地区要结合实际完善配套政策，促进产业转型升级。"
)
MIIT_TEXT = (
    "工业和信息化部发布新能源汽车产业发展规划。"
    "2025年上半年新能源汽车产量达1500万辆，同比增长12.5%。"
    "工信部将加快推动智能网联汽车产业化发展。"
)
GOV_EN_TEXT = (
    "The State Council issued guidelines on high-quality development of the "
    "new energy vehicle industry. Fiscal funds support charging infrastructure."
)


def _cfg(tmp_path) -> SourceConfig:
    return SourceConfig(db_path=tmp_path / "corpus.db")


def _seed(corpus: Corpus) -> None:
    corpus.upsert({"url": "https://www.gov.cn/", "site": "gov",
                   "org": "State Council, PRC", "lang": "zh",
                   "title": "中国政府网", "method": "ghosthand_live",
                   "fetched_at": 1700000000, "text": GOV_TEXT})
    corpus.upsert({"url": "https://www.miit.gov.cn/", "site": "miit",
                   "org": "MIIT", "lang": "zh", "title": "工业和信息化部",
                   "method": "ghosthand_live", "fetched_at": 1700000000,
                   "text": MIIT_TEXT})
    corpus.upsert({"url": "https://english.www.gov.cn/", "site": "gov",
                   "org": "State Council, PRC", "lang": "en",
                   "title": "English.gov.cn", "method": "requests_live",
                   "fetched_at": 1700000000, "text": GOV_EN_TEXT})


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    c = _cfg(tmp_path)
    monkeypatch.setattr(config, "_config", c)
    return c


# ---- research_query ----

def test_research_query_zh_terms_public(cfg):
    _seed(Corpus(cfg.db_path))
    out = research_query.research_query("new energy vehicle subsidy",
                                        query_zh="新能源汽车 补贴")
    assert out["dataQuality"] == "public"
    assert out["source"] == "corpus_cache"
    f = out["data"]["findings"]
    assert f and f[0]["site"] == "gov"
    # excerpt is a verbatim slice of the stored text
    assert f[0]["excerpt"] in GOV_TEXT
    assert f[0]["org"] == "State Council, PRC"
    assert f[0]["fetched_iso"] == time.strftime("%Y-%m-%d", time.localtime(1700000000))
    assert out["disclaimer"] and "not" in out["disclaimer"]


def test_research_query_doc_lang_filter(cfg):
    _seed(Corpus(cfg.db_path))
    out = research_query.research_query("new energy vehicle", doc_lang="en")
    assert all(x["doc_lang"] == "en" for x in out["data"]["findings"])
    assert out["data"]["findings"]


def test_research_query_empty_degrades(cfg):
    out = research_query.research_query("quantum flux capacitor")
    assert out["dataQuality"] == "degraded"
    assert out["data"]["findings"] == []
    assert out["data"]["gaps"]


# ---- cite_extract ----

def test_cite_extract_fetches_and_stores(cfg, monkeypatch):
    import src.sources.fetcher as fetcher
    rec = {"ok": True, "url": "https://www.stats.gov.cn/", "status": 200,
           "title": "国家统计局", "method": "ghosthand_live",
           "fetched_at": 1700000000, "text": "统计数据页面。" * 50}
    monkeypatch.setattr(fetcher, "fetch", lambda u, c, method="auto": rec)
    out = cite_extract.cite_extract("https://www.stats.gov.cn/")
    assert out["dataQuality"] == "live"
    cit = out["data"]["citation"]
    assert cit["org"] == "National Bureau of Statistics"
    assert cit["lang"] == "zh"
    assert cit["title"] == "国家统计局"
    # stored: second call (cache-only) answers from corpus
    out2 = cite_extract.cite_extract("https://www.stats.gov.cn/", live=False)
    assert out2["dataQuality"] == "public"
    assert out2["data"]["citation"]["url"] == cit["url"]


def test_cite_extract_unreachable_degrades(cfg, monkeypatch):
    import src.sources.fetcher as fetcher
    monkeypatch.setattr(fetcher, "fetch",
                        lambda u, c, method="auto": {"ok": False, "url": u,
                                                     "err": "requests: Timeout"})
    out = cite_extract.cite_extract("https://example.invalid/x")
    assert out["dataQuality"] == "degraded"
    assert "Timeout" in out["data"]["note"]
    assert out["data"]["citation"] is None


# ---- bilingual_brief ----

def test_bilingual_brief_skeleton(cfg):
    _seed(Corpus(cfg.db_path))
    out = bilingual_brief.bilingual_brief("新能源汽车补贴政策", query_zh="新能源汽车 补贴")
    assert out["dataQuality"] == "public"
    f = out["data"]["findings"][0]
    assert f["point_cn"] in GOV_TEXT          # verbatim
    assert f["citation"]["url"] == "https://www.gov.cn/"
    assert f["en_mirror"] == "https://english.www.gov.cn/"  # mirror in corpus
    miit = [x for x in out["data"]["findings"] if x["citation"]["url"].endswith("miit.gov.cn/")]
    if miit:
        assert miit[0]["en_mirror"] is None    # no mirror configured
    assert out["data"]["sources"]


def test_bilingual_brief_empty_gaps(cfg):
    out = bilingual_brief.bilingual_brief("nothing matches this")
    assert out["data"]["findings"] == []
    assert any("query_zh" in g or "seed" in g for g in out["data"]["gaps"])


# ---- data_table ----

def test_data_table_rows_cited(cfg):
    _seed(Corpus(cfg.db_path))
    out = data_table.data_table("新能源汽车产量与补贴", query_zh="新能源汽车 产量 补贴")
    rows = out["data"]["rows"]
    assert rows
    vals = {(r["value"], r["unit"]) for r in rows}
    assert ("120", "亿元") in vals
    assert ("1500", "万辆") in vals
    assert ("12.5", "%") in vals
    for r in rows:
        assert r["citation"]["url"]
        assert r["as_of"] == time.strftime("%Y-%m-%d", time.localtime(1700000000))
        assert r["context"]


def test_data_table_no_numbers_partial(cfg):
    corpus = Corpus(cfg.db_path)
    corpus.upsert({"url": "https://www.gov.cn/", "site": "gov", "org": "State Council, PRC",
                   "lang": "zh", "title": "t", "method": "requests_live",
                   "fetched_at": 1700000000, "text": "政策文件发布。无数字内容。"})
    out = data_table.data_table("政策", query_zh="政策")
    assert out["data"]["rows"] == []
    assert out["dataQuality"] == "partial"


# ---- locale ----

def test_locale_zh_disclaimer(cfg):
    _seed(Corpus(cfg.db_path))
    out = research_query.research_query("x", query_zh="新能源汽车", locale="zh")
    assert out["locale"] == "zh"
    assert "研究" in out["disclaimer"]


# ---- 2026-11-19 audit fixes: locale-correct fetch + real-English proof ----

def test_accept_language_for_url_role():
    from src.sources.fetcher import AL_EN, AL_ZH, accept_language_for
    assert accept_language_for("https://english.www.gov.cn/") == AL_EN
    assert accept_language_for("https://www.gov.cn/") == AL_ZH
    assert accept_language_for("https://www.miit.gov.cn/") == AL_ZH


def test_fetch_en_mirror_uses_english_headers(cfg, monkeypatch):
    import src.sources.fetcher as fetcher
    seen = {}

    class _Resp:
        status_code = 200
        encoding = "utf-8"
        apparent_encoding = "utf-8"
        text = "<html><head><title>EN</title></head><body>" \
               "The State Council issued new guidelines today." * 5 + "</body></html>"

        def json(self):
            return {}

    def fake_get(url, headers=None, timeout=None):
        seen["headers"] = headers or {}
        return _Resp()

    monkeypatch.setattr(fetcher.requests, "get", fake_get)
    rec = fetcher.fetch("https://english.www.gov.cn/", cfg, method="requests")
    assert rec["ok"] and rec["status"] == 200
    assert seen["headers"]["Accept-Language"].startswith("en")
    doc = fetcher.doc_from_fetch(rec)
    assert doc["lang"] in ("en", "mixed")
    assert fetcher.english_share(doc["text"]) >= 0.5


def test_en_mirror_requires_real_english_content(cfg):
    from src.sources import research as researchmod
    corpus = Corpus(cfg.db_path)
    # ZH-locale fetch of the EN portal: Chinese body + English nav -> NOT usable
    corpus.upsert({"url": "https://english.www.gov.cn/", "site": "gov",
                   "org": "State Council, PRC", "lang": "mixed", "title": "t",
                   "method": "ghosthand_live", "fetched_at": 1700000000,
                   "text": "习近平在中国深圳会见特朗普，两国领导人就经贸关系深入交换意见\n"
                           "国务院印发关于推动高质量发展的若干意见\n"
                           "Home\nNews\nServices\nLive & Work in China"})
    assert researchmod.en_mirror_for("gov", cfg) is None
    # real English content -> mirror offered
    corpus.upsert({"url": "https://english.www.gov.cn/", "site": "gov",
                   "org": "State Council, PRC", "lang": "en", "title": "t",
                   "method": "ghosthand_live", "fetched_at": 1700000000,
                   "text": "Xi welcomes Trump at Shenzhen airport\n"
                           "The State Council issued guidelines\n"
                           "LIVE & WORK IN CHINA\nSTUDY IN CHINA"})
    assert researchmod.en_mirror_for("gov", cfg) == "https://english.www.gov.cn/"


def test_en_mirror_falls_back_when_path_returns_chinese(cfg, monkeypatch):
    """Self-correcting: ghosthand serving the ZH body must not poison the
    corpus — fetch() retries via requests and only accepts real English."""
    import src.sources.fetcher as fetcher

    zh_rec = {"ok": True, "url": "https://english.www.gov.cn/", "status": 200,
              "title": "中华人民共和国国务院", "method": "ghosthand_live",
              "fetched_at": 1700000000,
              "text": "习近平在中国深圳会见特朗普\n国务院印发若干意见\nHome\nNews"}
    en_rec = {"ok": True, "url": "https://english.www.gov.cn/", "status": 200,
              "title": "English.gov.cn", "method": "requests_live",
              "fetched_at": 1700000000,
              "text": "Xi welcomes Trump at Shenzhen airport\n"
                      "The State Council issued new guidelines\n"
                      "LIVE & WORK IN CHINA"}
    monkeypatch.setattr(fetcher, "fetch_via_ghosthand", lambda u, c, al="": zh_rec)
    monkeypatch.setattr(fetcher, "fetch_via_requests", lambda u, c, al="": en_rec)
    rec = fetcher.fetch("https://english.www.gov.cn/", cfg)
    assert rec["method"] == "requests_live"      # poisoned path rejected
    assert fetcher.english_share(rec["text"]) >= 0.5


def test_ghosthand_404_is_not_success(cfg, monkeypatch):
    """A 404 page must never enter the corpus as content (audit finding)."""
    import src.sources.fetcher as fetcher
    import ghosthand as real_ghosthand

    class _Resp:
        status = 404

    class _Page:
        class context:
            @staticmethod
            def new_cdp_session(pg):
                class _C:
                    def send(self, *a, **k):
                        return {}

                return _C()

        def goto(self, url, **kw):
            return _Resp()

        def wait_for_timeout(self, ms):
            pass

        def evaluate(self, js):
            return {"title": "404", "text": "Not Found"}

    class _Driver:
        def __init__(self, **kw):
            pass

        def attach(self, **kw):
            return _Page()

        def close(self):
            pass

    fake = type(real_ghosthand)("ghosthand")
    fake.GhostDriver = _Driver
    monkeypatch.setitem(__import__("sys").modules, "ghosthand", fake)
    rec = fetcher.fetch_via_ghosthand("https://www.gov.cn/nope", cfg)
    assert rec["ok"] is False
    assert rec["status"] == 404
    assert "404" in rec["err"]