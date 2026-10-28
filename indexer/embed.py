# indexer/embed.py
"""Incremental, content-addressed embedding for the semantic package index.

Chunks are keyed by `chunk_hash` (see collect.chunk_hash). Vectors live in
index/vectors.npy; the sqlite table `vecrows(chunk_hash, row)` maps each hash
to its row in the npy. Only chunks whose hash has no vector yet are embedded,
so re-running collect + embed after a corpus update costs proportional to the
new/changed chunks, not the whole index.

Crash safety: vectors are appended and np.save'd per group of ~512 chunks,
then the vecrows rows for that group are committed. A crash between the two
leaves an unreferenced tail in the npy (harmless: the next run appends after
it); a crash before np.save leaves the map untouched. Rows whose chunk no
longer exists are "dead"; they are compacted away when they exceed a
fraction of the index.
"""
import argparse
import itertools
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from indexer.collect import chunk_hash

DEFAULT_GROUP_CHUNKS = 512
COMPACT_DEAD_FRACTION = 0.15
COMPACT_MIN_DEAD = 500


@dataclass
class EmbedStats:
    embedded: int
    reused: int
    dead_rows: int
    compacted: int = 0


def _l2norm(vecs: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    return np.divide(vecs, norms, out=np.zeros_like(vecs), where=norms > 0)


def _has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    return any(r[1] == column for r in conn.execute(f"PRAGMA table_info({table})"))


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone() is not None


def ensure_schema(index_dir: Path, legacy_next_row: int | None) -> sqlite3.Connection:
    """Create/upgrade chunks.db to the content-addressed schema.

    Legacy layout (id-aligned vectors, no chunk_hash) is migrated in place:
    hashes are computed for every row and vecrows is populated from the old
    positional alignment (row = id - 1) for ids covered by `legacy_next_row`
    (the pre-migration committed prefix; None means "everything").
    The migration runs inside one explicit transaction (DDL included), so a
    mid-way failure leaves the legacy table untouched.
    """
    conn = sqlite3.connect(index_dir / "chunks.db")
    conn.isolation_level = None  # explicit transaction control; DDL included
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("BEGIN IMMEDIATE")
    try:
        if not _table_exists(conn, "chunks"):
            conn.execute(
                "CREATE TABLE chunks("
                "id INTEGER PRIMARY KEY, chunk_hash TEXT NOT NULL UNIQUE, "
                "module TEXT NOT NULL, version TEXT NOT NULL, "
                "chunk_type TEXT NOT NULL, label TEXT, text TEXT NOT NULL)")
        elif not _has_column(conn, "chunks", "chunk_hash"):
            rows = conn.execute(
                "SELECT id, module, version, chunk_type, label, text FROM chunks"
                " ORDER BY id").fetchall()
            conn.execute("DROP TABLE chunks")
            conn.execute(
                "CREATE TABLE chunks("
                "id INTEGER PRIMARY KEY, chunk_hash TEXT NOT NULL UNIQUE, "
                "module TEXT NOT NULL, version TEXT NOT NULL, "
                "chunk_type TEXT NOT NULL, label TEXT, text TEXT NOT NULL)")
            seen: set[str] = set()
            deduped = []
            for r in rows:
                h = chunk_hash(r[1], r[2], r[3], r[4], r[5])
                if h in seen:
                    continue
                seen.add(h)
                deduped.append((r[0], h, *r[1:]))
            conn.executemany(
                "INSERT INTO chunks(id, chunk_hash, module, version, chunk_type,"
                " label, text) VALUES (?, ?, ?, ?, ?, ?, ?)", deduped)
            migrated_rows = [
                (h, rid - 1) for (rid, h, *_rest) in deduped
                if legacy_next_row is None or rid <= legacy_next_row
            ]
            if migrated_rows and Path(index_dir / "vectors.npy").is_file():
                conn.execute("DROP TABLE IF EXISTS vecrows")
                conn.execute(
                    "CREATE TABLE vecrows(chunk_hash TEXT PRIMARY KEY,"
                    " row INTEGER NOT NULL UNIQUE)")
                conn.executemany("INSERT INTO vecrows VALUES (?, ?)", migrated_rows)
            print(f"migrated legacy chunks.db: {len(rows)} rows -> {len(deduped)}"
                  f" unique, {len(migrated_rows)} vector mappings carried over")
        conn.execute("CREATE TABLE IF NOT EXISTS vecrows("
                     "chunk_hash TEXT PRIMARY KEY, row INTEGER NOT NULL UNIQUE)")
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        conn.close()
        raise
    return conn


def _read_legacy_next_row(state_dir: Path) -> int | None:
    import json
    path = state_dir / "index_state.json"
    if not path.is_file():
        return None
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    nr = state.get("next_row") if isinstance(state, dict) else None
    return int(nr) if isinstance(nr, int) and nr >= 0 else None


def embed(index_dir: Path, state_dir: Path, embedder, group_chunks: int = 512,
          compact_dead_fraction: float = COMPACT_DEAD_FRACTION,
          compact_min_dead: int = COMPACT_MIN_DEAD) -> EmbedStats:
    conn = ensure_schema(index_dir, _read_legacy_next_row(state_dir))
    vectors_path = index_dir / "vectors.npy"

    vecs: np.ndarray | None = None
    if vectors_path.is_file():
        vecs = np.load(vectors_path)
        if vecs.ndim != 2:
            raise RuntimeError(f"vectors.npy must be 2-D, got shape {vecs.shape}")
        # rows referenced beyond the npy cannot be trusted: unmap and re-embed
        conn.execute("DELETE FROM vecrows WHERE row >= ?", (len(vecs),))
        conn.commit()
    else:
        # no npy at all: every mapping is stale
        conn.execute("DELETE FROM vecrows")
        conn.commit()

    rows = conn.execute(
        "SELECT chunk_hash, module, version, text FROM chunks"
        " ORDER BY module, chunk_hash").fetchall()
    have = dict(conn.execute("SELECT chunk_hash, row FROM vecrows").fetchall())
    todo = [r for r in rows if r[0] not in have]
    live_hashes = {r[0] for r in rows}
    dead = [row for h, row in have.items() if h not in live_hashes]
    stats = EmbedStats(embedded=0, reused=len(rows) - len(todo), dead_rows=len(dead))

    group: list[tuple[str, str]] = []  # (hash, text)
    group_rows = 0

    def flush() -> None:
        nonlocal vecs, group, group_rows
        if not group:
            return
        start = 0 if vecs is None else len(vecs)
        new = _l2norm(np.asarray(embedder.embed([t for _, t in group]),
                                 dtype=np.float32))
        if len(new) != len(group):
            raise RuntimeError(
                f"embedder returned {len(new)} vectors for {len(group)} texts")
        vecs = new if vecs is None else np.concatenate([vecs, new], axis=0)
        np.save(vectors_path, vecs)
        conn.execute("BEGIN IMMEDIATE")
        conn.executemany(
            "INSERT OR REPLACE INTO vecrows VALUES (?, ?)",
            [(h, start + i) for i, (h, _) in enumerate(group)])
        conn.execute("COMMIT")
        stats.embedded += len(group)
        group, group_rows = [], 0

    for _hash, grp in itertools.groupby(todo, key=lambda r: r[1]):
        for r in grp:
            group.append((r[0], r[3]))
            group_rows += 1
            if group_rows >= group_chunks:
                flush()
    flush()

    # compaction: rewrite the npy without dead rows when they pile up
    dead_now = conn.execute(
        "SELECT COUNT(*) FROM vecrows WHERE chunk_hash NOT IN"
        " (SELECT chunk_hash FROM chunks)").fetchone()[0]
    total = 0 if vecs is None else len(vecs)
    if dead_now >= compact_min_dead and dead_now > compact_dead_fraction * total:
        live = conn.execute(
            "SELECT chunk_hash, row FROM vecrows WHERE chunk_hash IN"
            " (SELECT chunk_hash FROM chunks) ORDER BY row").fetchall()
        assert vecs is not None
        new_vecs = vecs[np.asarray([row for _, row in live], dtype=np.int64)]
        np.save(vectors_path, new_vecs)
        conn.execute("DELETE FROM vecrows")
        conn.executemany("INSERT INTO vecrows VALUES (?, ?)",
                         [(h, i) for i, (h, _) in enumerate(live)])
        conn.commit()
        stats.compacted = dead_now
        stats.dead_rows = 0
    conn.close()
    return stats


def main(argv=None):
    from indexer.api import GlmEmbedder
    ap = argparse.ArgumentParser(
        prog="python3 -m indexer.embed",
        description="Incrementally embed new/changed index chunks (resumable,"
                    " content-addressed; unchanged chunks are never re-embedded)")
    ap.add_argument("--index", type=Path, default=Path("index"))
    ap.add_argument("--state", type=Path, default=Path("state"))
    args = ap.parse_args(argv)
    print(embed(args.index, args.state, GlmEmbedder()))


if __name__ == "__main__":
    main()
