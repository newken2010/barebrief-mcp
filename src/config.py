"""Config: source registry + corpus cache + fetch policy.

Defaults are offline-safe: the corpus is a local SQLite cache; live fetch is
opt-in per call (`live=True`) and itself degrades to guidance when neither
GhostHand (CDP) nor plain requests can reach a source. Nothing is ever
fabricated — unverifiable pages simply do not enter the corpus.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from .sources.registry import SOURCES

_HERE = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("BAREFBRIEF_DATA", _HERE / "data"))


@dataclass
class SourceConfig:
    sources: list = field(default_factory=lambda: list(SOURCES))
    db_path: Path = field(default_factory=lambda: DATA_DIR / "corpus.db")
    cache_ttl_sec: int = 24 * 3600          # homepage snapshots refresh daily
    cdp_port: int = 9222                    # GhostHand attach port (Edge/Chrome)
    ghosthand_enabled: bool = True          # human-like fetch when browser is up
    requests_enabled: bool = True           # plain fallback (browser UA)
    request_timeout: int = 25
    max_text_chars: int = 20000             # per-doc cap stored in corpus


_config: SourceConfig | None = None


def get_config() -> SourceConfig:
    global _config
    if _config is None:
        _config = SourceConfig()
        DATA_DIR.mkdir(parents=True, exist_ok=True)
    return _config