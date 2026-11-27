"""Local corpus store: SQLite + dependency-free char-bigram keyword search.

Docs are homepage snapshots (or cite_extract-verified pages). Search scores by
character-bigram overlap, which works for Chinese without a segmenter and for
English words alike; cross-lingual matching is the caller's job (pass ZH
keywords as `query_zh` — see tool docs). Excerpts are verbatim slices around
the best-scoring window, so every finding is traceable to stored text.
"""
from __future__ import annotations

import re
import sqlite3
import time
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS docs(
    id INTEGER PRIMARY KEY,
    url TEXT UNIQUE,
    site TEXT,
    org TEXT,
    lang TEXT,
    title TEXT,
    method TEXT,
    fetched_at INTEGER,
    text TEXT
);
CREATE INDEX IF NOT EXISTS docs_site ON docs(site);
"""

_WS = re.compile(r"\s+")


def _bigrams(s: str) -> set:
    s = _WS.sub("", s.lower())
    if len(s) < 2:
        return {s} if s else set()
    return {s[i:i + 2] for i in range(len(s) - 1)}


def _terms(query: str) -> list:
    """Split a query into search terms: CJK runs stay whole, latin by word."""
    out, buf = [], ""
    for ch in query:
        if ch.isalnum() or ch in "-_":
            buf += ch
        else:
            if buf:
                out.append(buf)
            buf = ""
    if buf:
        out.append(buf)
    return [t for t in out if len(t) >= 2] or ([query] if query.strip() else [])


class Corpus:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self) -> None:
        with self._conn() as c:
            c.executescript(_SCHEMA)

    # ---------------- write ----------------

    def upsert(self, doc: dict) -> None:
        """Insert/replace a doc. `doc` keys: url, site, org, lang, title,
        method, fetched_at, text."""
        with self._conn() as c:
            c.execute(
                "INSERT INTO docs(url, site, org, lang, title, method, fetched_at, text)"
                " VALUES(?,?,?,?,?,?,?,?)"
                " ON CONFLICT(url) DO UPDATE SET site=excluded.site, org=excluded.org,"
                " lang=excluded.lang, title=excluded.title, method=excluded.method,"
                " fetched_at=excluded.fetched_at, text=excluded.text",
                (doc["url"], doc.get("site", ""), doc.get("org", ""),
                 doc.get("lang", ""), doc.get("title", ""), doc.get("method", ""),
                 int(doc.get("fetched_at", 0)), doc.get("text", "")),
            )

    def fresh_url(self, url: str, ttl_sec: int) -> dict | None:
        row = self.get(url)
        if row and (time.time() - row["fetched_at"]) < ttl_sec:
            return row
        return None

    # ---------------- read ----------------

    def get(self, url: str) -> dict | None:
        with self._conn() as c:
            r = c.execute("SELECT * FROM docs WHERE url=?", (url,)).fetchone()
            return dict(r) if r else None

    def all_docs(self, langs: tuple = ()) -> list:
        """All docs, optionally filtered to a set of languages.

        `langs` is a tuple like ("en", "mixed") — callers map a requested
        doc_lang to its usable group (mixed pages serve both).
        """
        with self._conn() as c:
            if langs:
                qs = ",".join("?" * len(langs))
                rows = c.execute(f"SELECT * FROM docs WHERE lang IN ({qs})",
                                 langs).fetchall()
            else:
                rows = c.execute("SELECT * FROM docs").fetchall()
            return [dict(r) for r in rows]

    def count(self) -> int:
        with self._conn() as c:
            return c.execute("SELECT COUNT(*) FROM docs").fetchone()[0]

    # ---------------- search ----------------

    def search(self, query: str, limit: int = 8, langs: tuple = ()) -> list:
        """Rank docs by bigram overlap; return per-doc best excerpt window.

        Score = matched-term bigrams / query bigrams (0..1). Excerpt is the
        verbatim text window (±160 chars) around the densest hit.
        `langs`: tuple of acceptable doc languages (() = any).
        """
        terms = _terms(query)
        if not terms:
            return []
        q_bi = _bigrams("".join(terms))
        if not q_bi:
            return []
        hits = []
        for doc in self.all_docs(langs=langs):
            text = doc.get("text") or ""
            if not text:
                continue
            t_bi = _bigrams(text)
            if not t_bi:
                continue
            inter = len(q_bi & t_bi)
            if inter == 0:
                continue
            score = inter / len(q_bi)
            excerpt, where = self._best_window(text, terms)
            hits.append({**doc, "score": round(score, 4), "excerpt": excerpt,
                         "excerpt_at": where})
        hits.sort(key=lambda h: (-h["score"], -h["fetched_at"]))
        return hits[:limit]

    @staticmethod
    def _best_window(text: str, terms: list, half: int = 160) -> tuple:
        low = text.lower()
        best_pos, best_n = -1, -1
        for t in terms:
            start = 0
            tl = t.lower()
            while True:
                p = low.find(tl, start)
                if p < 0:
                    break
                # count how many terms co-occur in this window
                win = low[max(0, p - half):p + half]
                n = sum(1 for x in terms if x.lower() in win)
                if n > best_n:
                    best_n, best_pos = n, p
                start = p + 1
        if best_pos < 0:
            return text[: half * 2].strip(), 0
        a = max(0, best_pos - half)
        b = min(len(text), best_pos + half)
        return text[a:b].strip(), a