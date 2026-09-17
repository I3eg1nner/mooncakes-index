# indexer/testing.py
"""Shared test fixtures for the indexer package.

Home of the deterministic FakeEmbedder and the index/state builders.
test_embed.py uses them today; Tasks 4-6 import from here as well.
"""
import hashlib
import json
import sqlite3

import numpy as np


class FakeEmbedder:
    """确定性 fake：sha256(text) 前 4 字节归一化为向量，并记录每次调用。"""

    def __init__(self):
        self.calls = []

    def embed(self, texts):
        self.calls.append(list(texts))
        vecs = []
        for t in texts:
            raw = np.frombuffer(hashlib.sha256(t.encode()).digest()[:4], dtype=np.uint8)
            v = raw.astype(np.float32) / 255.0
            vecs.append(v / max(np.linalg.norm(v), 1e-9))
        return np.stack(vecs)


def build_index(tmp_path, modules):
    """modules: {name: (version, [chunk_texts])}；返回 (index_dir, state_dir)。"""
    index_dir = tmp_path / "index"
    index_dir.mkdir()
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    db = sqlite3.connect(index_dir / "chunks.db")
    db.execute("CREATE TABLE chunks(id INTEGER PRIMARY KEY, module TEXT, version TEXT,"
               " chunk_type TEXT, label TEXT, text TEXT)")
    for name, (version, texts) in modules.items():
        for t in texts:
            db.execute("INSERT INTO chunks(module, version, chunk_type, label, text)"
                       " VALUES (?,?,?,?,?)", (name, version, "meta", None, t))
    db.commit()
    db.close()
    return index_dir, state_dir


def write_state(state_dir, next_row, sha):
    (state_dir / "index_state.json").write_text(json.dumps(
        {"chunks_sha": sha, "next_row": next_row, "modules": {}}))


def chunks_sha(index_dir):
    return hashlib.sha256((index_dir / "chunks.db").read_bytes()).hexdigest()
