# indexer/test_search.py
import json
import sqlite3

import numpy as np
import pytest

import indexer.search as search
from indexer.search import load_verdicts
from indexer.testing import (FakeEmbedder, attach_vectors, build_index,
                             write_results)


def test_load_verdicts_missing_and_present(tmp_path):
    f = tmp_path / "results.jsonl"
    f.write_text(json.dumps({"module": "a/b", "version": "1.0.0", "verdict": "Clean", "risk": 0}) + "\n")
    v = load_verdicts(f)
    assert v["a/b"]["verdict"] == "Clean"
    assert v.get("x/y") is None


def test_search_ranks_expected_module_top(tmp_path):
    # fixture：2 模块 × 1 chunk；FakeEmbedder 使 query 向量 = "moonjq" chunk 向量
    index_dir, state_dir = build_index(tmp_path, {
        "bobzhang/moonjq": ("0.1.2", ["jq jmespath json query"]),
        "evil/pwn": ("9.9.9", ["malicious payload"]),
    })
    attach_vectors(index_dir)

    class QueryIsJq(FakeEmbedder):
        def embed(self, texts):
            return FakeEmbedder().embed(["jq jmespath json query"])  # query≈moonjq chunk

    hits = search.search("jmes", n=5, verdict=None, index_dir=index_dir,
                         results_path=tmp_path / "results.jsonl", embedder=QueryIsJq())
    assert hits[0].module == "bobzhang/moonjq" and hits[0].score == pytest.approx(1.0 * search.META_BOOST, abs=1e-6)


def test_search_empty_query_raises(tmp_path):
    with pytest.raises(ValueError):
        search.search("", n=5, verdict=None, index_dir=tmp_path,
                      results_path=tmp_path / "r.jsonl", embedder=FakeEmbedder())


def test_search_verdict_filter(tmp_path):
    # evil/pwn 标记 Malicious → --verdict clean 后结果只剩 moonjq
    index_dir, _ = build_index(tmp_path, {
        "bobzhang/moonjq": ("0.1.2", ["jq jmespath json query"]),
        "evil/pwn": ("9.9.9", ["malicious payload"]),
    })
    attach_vectors(index_dir)
    (tmp_path / "results.jsonl").write_text(json.dumps(
        {"module": "evil/pwn", "version": "9.9.9", "verdict": "Malicious", "risk": 9}) + "\n")
    hits = search.search("jmes", n=5, verdict="clean", index_dir=index_dir,
                         results_path=tmp_path / "results.jsonl", embedder=FakeEmbedder())
    assert all(h.verdict != "Malicious" for h in hits)


def test_search_rejects_bad_n(tmp_path):
    index_dir, _ = build_index(tmp_path, {"a/x": ("1.0.0", ["t"])})
    attach_vectors(index_dir)
    with pytest.raises(ValueError):
        search.search("t", n=0, verdict=None, index_dir=index_dir,
                      results_path=tmp_path / "r.jsonl", embedder=FakeEmbedder())


def test_meta_chunk_boosted_in_aggregation(tmp_path):
    index_dir, _ = build_index(tmp_path, {
        "a/mod": ("1.0.0", ["author self description of the module"]),
        "b/mod": ("2.0.0", ["readme body text of the module"]),
    })
    attach_vectors(index_dir)
    import sqlite3 as _sq
    _db = _sq.connect(index_dir / "chunks.db")
    _db.execute("UPDATE chunks SET chunk_type = 'readme' WHERE module = 'b/mod'")
    _db.commit()
    _db.close()

    class QueryIsMeta(FakeEmbedder):
        def embed(self, texts):
            return FakeEmbedder().embed(["author self description of the module"])

    hits = search.search("meta", n=5, verdict=None, index_dir=index_dir,
                         results_path=tmp_path / "results.jsonl", embedder=QueryIsMeta())
    assert hits[0].module == "a/mod" and hits[1].module == "b/mod"
    assert hits[0].score == pytest.approx(1.0 * search.META_BOOST, abs=1e-6)
    assert hits[1].score < hits[0].score


def test_description_prefers_registry(tmp_path):
    # build_index(tmp_path) 无 modules 时返回单个 index_dir（STUB_CORPUS 桩索引）
    index_dir = build_index(tmp_path)
    results_path = write_results(tmp_path)
    first = sqlite3.connect(index_dir / "chunks.db").execute(
        "SELECT module FROM chunks ORDER BY id LIMIT 1").fetchone()[0]
    reg = tmp_path / "registry.json"
    reg.write_text(json.dumps([{"name": first, "description": "REGISTRY DESC"}]))

    kw = dict(n=5, verdict=None, index_dir=index_dir,
              results_path=results_path, embedder=FakeEmbedder())

    hits = search.search("jmes", registry_path=reg, **kw)
    hit = next(h for h in hits if h.module == first)
    assert hit.description == "REGISTRY DESC"

    hits_none = search.search("jmes", registry_path=None, **kw)
    hit_none = next(h for h in hits_none if h.module == first)
    assert hit_none.description != "REGISTRY DESC"  # 回退块文本
