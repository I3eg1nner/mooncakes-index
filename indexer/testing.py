# indexer/testing.py
"""Shared test fixtures for the indexer package.

Home of the deterministic FakeEmbedder and the index/state builders.
test_embed.py uses them today; Tasks 4-6 import from here as well.
"""
import hashlib
import json
import sqlite3

import numpy as np

# Stub corpus used by build_index(tmp_path) (no modules given): a clean
# module whose chunks mention "jmes"/"jq" plus a malicious one, so serve/
# search tests have something meaningful to rank and to join verdicts for.
STUB_CORPUS = {
    "bobzhang/moonjq": ("0.1.2", ["jq jmespath json query"]),
    "evil/pwn": ("9.9.9", ["malicious payload"]),
}


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


def build_index(tmp_path, modules=None):
    """modules: {name: (version, [chunk_texts])}；返回 (index_dir, state_dir)。

    modules=None 时写入 STUB_CORPUS 桩索引（chunks.db + vectors.npy +
    state/registry_index.json 缓存桩）并直接返回 index_dir（供 serve 测试使用）。
    """
    if modules is None:
        modules = STUB_CORPUS
        index_dir, state_dir = _write_index(tmp_path, modules, with_vectors=True)
        registry = [{"name": name, "version": version, "description": texts[0]}
                    for name, (version, texts) in modules.items()]
        (state_dir / "registry_index.json").write_text(
            json.dumps(registry, ensure_ascii=False), encoding="utf-8")
        return index_dir
    return _write_index(tmp_path, modules, with_vectors=False)


def _write_index(tmp_path, modules, with_vectors):
    index_dir = tmp_path / "index"
    index_dir.mkdir()
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    db = sqlite3.connect(index_dir / "chunks.db")
    db.execute("CREATE TABLE chunks(id INTEGER PRIMARY KEY, module TEXT, version TEXT,"
               " chunk_type TEXT, label TEXT, text TEXT)")
    texts_in_order = []
    for name, (version, texts) in modules.items():
        for t in texts:
            db.execute("INSERT INTO chunks(module, version, chunk_type, label, text)"
                       " VALUES (?,?,?,?,?)", (name, version, "meta", None, t))
            texts_in_order.append(t)
    db.commit()
    db.close()
    if with_vectors:
        np.save(index_dir / "vectors.npy", FakeEmbedder().embed(texts_in_order))
    return index_dir, state_dir


def write_state(state_dir, next_row, sha):
    (state_dir / "index_state.json").write_text(json.dumps(
        {"chunks_sha": sha, "next_row": next_row, "modules": {}}))


def write_results(tmp_path):
    """写 results.jsonl 审计桩（覆盖 STUB_CORPUS 的两个模块），返回其路径。"""
    path = tmp_path / "results.jsonl"
    records = [
        {"module": "bobzhang/moonjq", "version": "0.1.2", "verdict": "Clean", "risk": 0},
        {"module": "evil/pwn", "version": "9.9.9", "verdict": "Malicious", "risk": 9},
    ]
    path.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records),
        encoding="utf-8")
    return path


def chunks_sha(index_dir):
    return hashlib.sha256((index_dir / "chunks.db").read_bytes()).hexdigest()
