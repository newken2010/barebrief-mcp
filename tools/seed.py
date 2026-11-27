"""Seed the corpus: fetch every registry source (homes + EN mirrors).

Run:  python tools/seed.py [--force]

Idempotent: fresh docs (within cache TTL) are skipped; --force refetches all.
Human-paced when GhostHand (Edge/Chrome on CDP 9222) answers; plain requests
otherwise. Failures are reported per site and never block the others.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from src.config import get_config  # noqa: E402
from src.sources import fetcher, registry  # noqa: E402
from src.sources.store import Corpus  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="seed bilingual-research corpus")
    ap.add_argument("--force", action="store_true", help="refetch even if fresh")
    args = ap.parse_args()

    cfg = get_config()
    corpus = Corpus(cfg.db_path)
    ok = fail = skipped = 0

    for src in registry.SOURCES:
        for url in (src["home"], src.get("en") or ""):
            if not url:
                continue
            if not args.force and corpus.fresh_url(url, cfg.cache_ttl_sec):
                print(f"SKIP {src['key']:7s} {url} (fresh)")
                skipped += 1
                continue
            t0 = time.time()
            rec = fetcher.fetch(url, cfg)
            if rec.get("ok") and rec.get("text"):
                doc = fetcher.doc_from_fetch(rec)
                corpus.upsert(doc)
                ok += 1
                print(f"OK   {src['key']:7s} {url}  "
                      f"[{rec['method']}] {rec.get('title', '')[:40]} | "
                      f"{len(rec['text'])} chars | {time.time() - t0:.1f}s")
            else:
                fail += 1
                print(f"FAIL {src['key']:7s} {url}  {rec.get('err', 'empty body')[:80]}")

    print(f"\n===== seed done: {ok} ok / {skipped} skipped / {fail} failed; "
          f"corpus={corpus.count()} docs -> {cfg.db_path} =====")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())