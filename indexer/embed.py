# indexer/embed.py
"""Batch embedding for the semantic package index.

Vectorizes un-embedded chunks from index/chunks.db module-by-module (one
embedder.embed(texts) call per module), appends L2-normalized rows to
index/vectors.npy (npy row i holds the vector for chunks.id = i + 1), and
checkpoints progress in state/index_state.json after each module so an
interrupted run can resume. A chunks.db that no longer matches the
checkpointed chunks_sha (collect was re-run) raises StaleIndexError: the
index must be rebuilt from scratch.
"""
import argparse
import hashlib
import itertools
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import numpy as np


class StaleIndexError(RuntimeError):
    """chunks.db changed since the last embed run; delete index/vectors.npy and
    state/index_state.json, then re-run embed."""


@dataclass
class EmbedStats:
    modules_done: int
    chunks_done: int
    skipped: int


def _l2norm(vecs: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    return np.divide(vecs, norms, out=np.zeros_like(vecs), where=norms > 0)


def _read_state(state_dir: Path) -> dict | None:
    path = state_dir / "index_state.json"
    if not path.is_file():
        return None
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(state, dict) or not isinstance(state.get("chunks_sha"), str):
        return None
    return state


def _write_state(state_dir: Path, state: dict) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "index_state.json").write_text(
        json.dumps(state, ensure_ascii=False), encoding="utf-8")


def embed(index_dir: Path, state_dir: Path, embedder) -> EmbedStats:
    db_path = index_dir / "chunks.db"
    sha = hashlib.sha256(db_path.read_bytes()).hexdigest()
    state = _read_state(state_dir)
    if state is not None and state.get("chunks_sha") != sha:
        raise StaleIndexError(
            f"chunks.db changed since the last embed run "
            f"(state sha {state['chunks_sha'][:12]}... != current {sha[:12]}...); "
            "delete index/vectors.npy and state/index_state.json, then re-run embed"
        )
    next_row = int(state.get("next_row") or 0) if state is not None else 0
    if next_row < 0:
        raise StaleIndexError(
            f"corrupt checkpoint: next_row={next_row} is negative; "
            "delete index/vectors.npy and state/index_state.json, then re-run embed"
        )

    vectors_path = index_dir / "vectors.npy"
    vecs = None
    if vectors_path.is_file():
        vecs = np.load(vectors_path)
        if vecs.ndim != 2:
            raise RuntimeError(f"vectors.npy must be 2-D, got shape {vecs.shape}")
        if len(vecs) > next_row:
            vecs = vecs[:next_row]  # rollback a half-written module
        elif len(vecs) < next_row:
            next_row = len(vecs)  # defensive: trust the npy, not the state
    elif next_row > 0:
        # Checkpoint claims committed rows, but vectors.npy is gone: the index is
        # inconsistent — rebuild it in full (the safe, converging direction).
        next_row = 0

    stats = EmbedStats(0, 0, 0)
    modules: dict = {}
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT id, module, version, text FROM chunks ORDER BY id").fetchall()
    finally:
        conn.close()

    for module, grp in itertools.groupby(rows, key=lambda r: r[1]):
        grp = list(grp)
        start = grp[0][0] - 1  # npy row for chunks.id (ids are 1-based)
        end = grp[-1][0]  # exclusive row position after this module
        modules[module] = {"version": grp[0][2], "chunks": len(grp)}
        if end <= next_row:
            stats.skipped += len(grp)
            continue
        if start != (0 if vecs is None else len(vecs)):
            raise RuntimeError(
                f"row misalignment: module {module!r} would write at row {start} "
                f"but vectors.npy has {0 if vecs is None else len(vecs)} committed rows"
            )
        new = _l2norm(np.asarray(embedder.embed([r[3] for r in grp]), dtype=np.float32))
        vecs = new if vecs is None else np.concatenate([vecs, new], axis=0)
        np.save(vectors_path, vecs)
        next_row = end
        _write_state(state_dir, {"chunks_sha": sha, "next_row": next_row,
                                 "modules": modules})
        stats.chunks_done += len(grp)
        stats.modules_done += 1
    return stats


def main(argv=None):
    from indexer.api import GlmEmbedder
    ap = argparse.ArgumentParser(
        prog="python3 -m indexer.embed",
        description="Embed un-embedded index chunks with GLM embedding-3 (resumable)")
    ap.add_argument("--index", type=Path, default=Path("index"))
    ap.add_argument("--state", type=Path, default=Path("state"))
    args = ap.parse_args(argv)
    print(embed(args.index, args.state, GlmEmbedder()))


if __name__ == "__main__":
    main()
