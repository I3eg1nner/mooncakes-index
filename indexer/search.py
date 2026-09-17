# indexer/search.py
"""Semantic retrieval over the package index.

Loads index/vectors.npy + index/chunks.db, embeds the query with the given
Embedder, scores every chunk by cosine similarity (vectors are L2-normalized
at write time, so a normalized dot product is the cosine), aggregates per
module by its max chunk score, joins verdict/risk from the audit results
jsonl, optionally filters by verdict (case-insensitive, after the join),
and returns up to n hits sorted by score desc (module name as tie-break).
"""
import argparse
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import numpy as np

MAX_QUERY_CHARS = 512


@dataclass
class Hit:
    module: str
    version: str
    score: float
    verdict: str | None
    risk: int | None
    description: str


def load_verdicts(results_path: Path) -> dict[str, dict]:
    """Parse the audit results jsonl into {module: {"verdict","risk","version"}}.

    A missing file yields {} (search still works, verdicts/risk are None).
    """
    if not results_path.is_file():
        return {}
    out: dict[str, dict] = {}
    for line in results_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        name = rec.get("module")
        if name:
            out[name] = {"verdict": rec.get("verdict"), "risk": rec.get("risk"),
                         "version": rec.get("version")}
    return out


def _load_chunks(index_dir: Path) -> list[tuple]:
    conn = sqlite3.connect(index_dir / "chunks.db")
    try:
        return conn.execute(
            "SELECT id, module, version, text FROM chunks ORDER BY id").fetchall()
    finally:
        conn.close()


def search(query: str, *, n: int = 10, verdict: str | None, index_dir: Path,
           results_path: Path, embedder) -> list[Hit]:
    if n < 1:
        raise ValueError("n must be >= 1")
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must be a non-empty string")
    if len(query) > MAX_QUERY_CHARS:
        raise ValueError(f"query longer than {MAX_QUERY_CHARS} characters")

    rows = _load_chunks(index_dir)
    if not rows:
        return []
    vecs = np.load(index_dir / "vectors.npy")

    qv = np.asarray(embedder.embed([query]), dtype=np.float32)[0]
    norm = float(np.linalg.norm(qv))
    if norm > 0:
        qv = qv / norm

    best: dict[str, tuple[float, str, str]] = {}
    for cid, module, version, text in rows:
        row = cid - 1  # npy row i holds the vector for chunks.id = i + 1
        if row < 0 or row >= len(vecs):
            continue
        score = float(vecs[row] @ qv)
        cur = best.get(module)
        if cur is None or score > cur[0]:
            best[module] = (score, version, text)

    verdicts = load_verdicts(results_path)
    hits = [Hit(module=m, version=v, score=s, verdict=(verdicts.get(m) or {}).get("verdict"),
                risk=(verdicts.get(m) or {}).get("risk"), description=d)
            for m, (s, v, d) in best.items()]
    hits.sort(key=lambda h: (-h.score, h.module))
    if verdict is not None:
        want = verdict.strip().lower()
        hits = [h for h in hits
                if h.verdict is not None and h.verdict.lower() == want]
    return hits[:n]


def main(argv=None):
    from indexer.api import GlmEmbedder
    ap = argparse.ArgumentParser(
        prog="python3 -m indexer.search",
        description="Semantic search over the MoonBit package index")
    ap.add_argument("query", help="natural-language query")
    ap.add_argument("-n", type=int, default=10, help="max results (default 10)")
    ap.add_argument("--verdict", default=None,
                    help="filter by verdict, e.g. clean (case-insensitive)")
    ap.add_argument("--json", action="store_true", help="output JSON instead of a table")
    ap.add_argument("--index-dir", type=Path, default=Path("index"))
    ap.add_argument("--results", type=Path, default=Path("results/results.jsonl"))
    args = ap.parse_args(argv)
    hits = search(args.query, n=args.n, verdict=args.verdict,
                  index_dir=args.index_dir, results_path=args.results,
                  embedder=GlmEmbedder())
    if args.json:
        print(json.dumps([h.__dict__ for h in hits], ensure_ascii=False))
        return
    for h in hits:
        print(f"{h.score:.4f} | {h.module} | {h.verdict or '-'} | {h.description[:70]}")


if __name__ == "__main__":
    main()
