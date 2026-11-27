# barebrief — bilingual research brief MCP

[![mcp-bilingual-research-brief MCP server](https://glama.ai/mcp/servers/newken2010/mcp-bilingual-research-brief/badges/score.svg)](https://glama.ai/mcp/servers/newken2010/mcp-bilingual-research-brief)

**中英双语调研简报 MCP**：面向英文 Agent/买家的中国官方信源检索与引文工具。
问题进来 → 逐字中文摘录 + 可追溯引文 + 官方英文门户（有则给）→ 英文行文由调用方
Agent 自己写。我们保证的是**来源真实、摘录逐字、引文可核**，绝不代笔、绝不编造。

Brand: **Brief（简报）** · License: MIT · Python 3.11+ · 依赖：fastmcp / requests

## 工具（4 个）

| 工具 | 作用 | 关键输出 |
|---|---|---|
| `research_query` | 主题 → 排序后的逐字摘录 + 引文 | findings[]: excerpt / url / org / fetched_at |
| `cite_extract` | URL → 规范引文记录（先核后引） | citation: title / org / lang / excerpt |
| `bilingual_brief` | 问题 → 中英简报骨架 | findings[]: point_cn(逐字) + citation + en_mirror |
| `data_table` | 问题 → 带引用的数字行 | rows[]: value + unit + context + as_of + on_topic |

## 数据与抓取

- **语料**：本地 SQLite（`data/corpus.db`），缓存 6 个中国官方源首页 + gov 英文门户。
  每个文档记录 url / org / fetched_at / 抓取方式（ghosthand_live / requests_live）。
- **抓取三级**：缓存 → GhostHand（拟人 CDP，过墙）→ 普通 requests。**按 URL
  角色分发请求头**：英文镜像用英文优先（该门户按 Accept-Language 协商发中/英
  内容，中文头会静默拿到中文正文——2026-11-19 实测），中文首页用中文优先；
  EN 镜像抓取后还过 `english_share ≥ 0.5` 验证，不过就换路径重抓，毒文档不进库。
- **红线**：摘录一律逐字切片；数字不做换算不做插值；抓不到的页老实降级
  （dataQuality=degraded + 原因），不存在"猜一个引文"。

## 使用

```bash
pip install -e .                    # 或 poetry/pdm 等效
python tools/seed.py                # 灌语料（GhostHand 优先，需 Edge/CDP 9222）
python tools/demo.py                # 三个工具各跑一次真实 query 看效果
python main.py                      # 起 stdio MCP server
pytest tests/ -q                    # 离线测试（10 项，mock 抓取）
```

MCP 客户端配置（stdio）：

```json
{"mcpServers": {"brief": {"command": "python",
 "args": ["main.py"], "cwd": "/path/to/mcp-bilingual-research-brief"}}}
```

## 给调用方 Agent 的提示（写进你的 system prompt）

1. 中文语料召回低？把问题翻成中文关键词传 `query_zh`（如 "新能源汽车 补贴"）。
2. 要写英文简报：用 `bilingual_brief` 拿骨架，`point_cn` 逐字引用 + citation，
   英文行文你自己写；`en_mirror` 非空时优先引英文官方页。
3. 要数字：`data_table` 的行已带 `as_of`（抓取日）和引文；`on_topic=True` 的行
   句子含查询词，排序在前。
4. 首页快照不够深：从 findings 拿文章 URL，用 `cite_extract` 核过再引。
5. `live=True` 会现抓（拟人节奏，慢但新）；平时用缓存（dataQuality=public）。

## 合规

所有输出带 disclaimer：**研究支持，非建议**；引文均来自公开官方来源；
数字为原文逐字 + as_of 日期，决策前须回原页面核对。不抓需登录/付费墙内容，
不存 A 股等不出门数据（本 MCP 只碰公开 CN 语料）。

## 目录

```
main.py                 FastMCP 入口（4 工具注册）
src/config.py           语料库/CDP/缓存 TTL 配置
src/envelope.py         统一信封 + dataQuality + 免责声明（en/zh）
src/sources/registry.py 官方源登记表（6 站 + gov EN 门户，均实测过）
src/sources/store.py    SQLite 语料 + 二元（bigram）检索，逐字摘录
src/sources/fetcher.py  缓存→GhostHand→requests 三级抓取 + 内容语言检测
src/sources/research.py 检索/实时刷新/质量分级共享逻辑
src/tools/              4 个工具（薄封装）
tools/seed.py           灌语料；tools/demo.py 三工具演示
tests/                  离线测试（mock 抓取，10 项）
```