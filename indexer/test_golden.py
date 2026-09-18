# indexer/test_golden.py
"""Golden acceptance: querying "jmes" surfaces jq-family JSON-query tools in top-5."""
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
    # intent: searching "jmes" must surface jq-family JSON-query tools (moonjq's tokenizer-obscured name can't be pinned literally; see task-6 report ruling)
    JQ_FAMILY = {"bobzhang/moonjq", "shina1024/jqx", "bobzhang/jq", "cli/jq", "cli/jqlog", "bobzhang/jqlog"}
    top = {h.module for h in hits}
    assert len(top & JQ_FAMILY) >= 3, f"jq-family modules missing from top-5: {top}"
