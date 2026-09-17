# indexer/test_api.py
import numpy as np
import pytest
from indexer import api


def test_missing_key_raises(monkeypatch):
    monkeypatch.delenv("ZHIPUAI_API_KEY", raising=False)
    with pytest.raises(api.MissingKeyError):
        api.GlmEmbedder()


def test_normalizes_and_stacks(monkeypatch):
    monkeypatch.setenv("ZHIPUAI_API_KEY", "test-key")

    captured = {}

    def fake_post(url, payload, key):
        captured["url"], captured["payload"], captured["key"] = url, payload, key
        vecs = [[3.0, 4.0], [0.0, 0.0]]
        return {"data": [{"embedding": v, "index": i} for i, v in enumerate(vecs)]}

    monkeypatch.setattr(api, "_post", fake_post)
    out = api.GlmEmbedder(dims=2, batch_size=2).embed(["a", "b"])

    assert captured["url"] == api.GLM_URL
    assert captured["key"] == "test-key"
    assert captured["payload"] == {"model": "embedding-3", "input": ["a", "b"], "dimensions": 2}
    assert out.shape == (2, 2)
    assert out.dtype == np.float32
    np.testing.assert_allclose(np.linalg.norm(out, axis=1), [1.0, 0.0])
    # 零向量不产生 NaN
    assert np.isfinite(out).all()
