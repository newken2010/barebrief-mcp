"""端到端实测：三个工具各跑一次真实 query（语料已灌）。"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from src.tools import bilingual_brief, data_table, research_query  # noqa: E402

print("=== 1) research_query(query_zh=新能源汽车 补贴) ===")
r = research_query.research_query("China NEV subsidy policy", query_zh="新能源汽车 补贴")
print("quality:", r["dataQuality"], "| source:", r["source"], "| docs:", r["data"]["corpus_docs"])
for f in r["data"]["findings"][:3]:
    print(f"  [{f['site']}/{f['doc_lang']}] score={f['score']} {f['title'][:30]}")
    print(f"    url: {f['url']}")
    print(f"    excerpt: {f['excerpt'][:100]}")
print("  gaps:", r["data"]["gaps"])

print("\n=== 2) bilingual_brief(query_zh=招标 采购) ===")
b = bilingual_brief.bilingual_brief("government procurement trends", query_zh="招标 采购")
print("quality:", b["dataQuality"])
for f in b["data"]["findings"][:2]:
    print(f"  point_cn: {f['point_cn'][:80]}")
    print(f"  citation: {f['citation']['org']} | {f['citation']['url']} | {f['citation']['fetched_iso']}")
    print(f"  en_mirror: {f['en_mirror']}")

print("\n=== 3) data_table(query_zh=经济 增长 产量) ===")
t = data_table.data_table("economic growth output", query_zh="经济增长 产量 数据")
print("quality:", t["dataQuality"])
for row in t["data"]["rows"][:6]:
    print(f"  {row['value']}{row['unit']}  <- {row['citation']['org']} ({row['as_of']})")
    print(f"    ctx: {row['context'][:70]}")