# indexer/test_search.py
import json

import numpy as np
import pytest

import indexer.search as search
from indexer.search import load_verdicts
from indexer.testing import FakeEmbedder, build_index


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
    np.save(index_dir / "vectors.npy", FakeEmbedder().embed(
        ["jq jmespath json query", "malicious payload"]))

    class QueryIsJq(FakeEmbedder):
        def embed(self, texts):
            return FakeEmbedder().embed(["jq jmespath json query"])  # query≈moonjq chunk

    hits = search.search("jmes", n=5, verdict=None, index_dir=index_dir,
                         results_path=tmp_path / "results.jsonl", embedder=QueryIsJq())
    assert hits[0].module == "bobzhang/moonjq" and hits[0].score == pytest.approx(1.0, abs=1e-6)


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
    np.save(index_dir / "vectors.npy", FakeEmbedder().embed(
        ["jq jmespath json query", "malicious payload"]))
    (tmp_path / "results.jsonl").write_text(json.dumps(
        {"module": "evil/pwn", "version": "9.9.9", "verdict": "Malicious", "risk": 9}) + "\n")
    hits = search.search("jmes", n=5, verdict="clean", index_dir=index_dir,
                         results_path=tmp_path / "results.jsonl", embedder=FakeEmbedder())
    assert all(h.verdict != "Malicious" for h in hits)


def test_search_rejects_bad_n(tmp_path):
    index_dir, _ = build_index(tmp_path, {"a/x": ("1.0.0", ["t"])})
    np.save(index_dir / "vectors.npy", FakeEmbedder().embed(["t"]))
    with pytest.raises(ValueError):
        search.search("t", n=0, verdict=None, index_dir=index_dir,
                      results_path=tmp_path / "r.jsonl", embedder=FakeEmbedder())
