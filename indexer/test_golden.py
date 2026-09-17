# indexer/test_golden.py
import os
from pathlib import Path
import pytest
from indexer import api, search
from indexer.collect import collect
from indexer.embed import embed

pytestmark = pytest.mark.skipif(
    not os.environ.get("ZHIPUAI_API_KEY"), reason="needs ZHIPUAI_API_KEY")


def test_golden_jmes(tmp_path):
    collect(Path("corpus"), tmp_path / "index", tmp_path / "state")
    embed(tmp_path / "index", tmp_path / "state", api.GlmEmbedder())
    hits = search.search("jmes", n=5, verdict=None,
                         index_dir=tmp_path / "index",
                         results_path=Path("results/results.jsonl"),
                         embedder=api.GlmEmbedder())
    assert "bobzhang/moonjq" in {h.module for h in hits}
