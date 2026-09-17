# indexer/test_embed.py
import json

import numpy as np
import pytest

from indexer import api as api_mod
from indexer import embed as embed_mod
from indexer.api import MissingKeyError
from indexer.testing import FakeEmbedder, build_index, chunks_sha, write_state


def test_embed_resume_and_rollback(tmp_path):
    mods = {"a/x": ("1.0.0", ["ax"]), "b/y": ("2.0.0", ["by1", "by2"])}
    index_dir, state_dir = build_index(tmp_path, mods)

    # 无 checkpoint：全量 3 chunk；npy 行 i 保存 chunks.id = i+1 的向量（SQLite id 从 1 起，行号紧凑）
    fake = FakeEmbedder()
    st = embed_mod.embed(index_dir, state_dir, fake)
    assert st.chunks_done == 3 and st.skipped == 0
    v = np.load(index_dir / "vectors.npy")
    assert v.shape == (3, 4)
    # npy 行 i 与 chunks.id=i+1 对齐：第 0 行应可由 FakeEmbedder 对 a/x 首块重算复现
    expect = FakeEmbedder().embed(["ax"])
    np.testing.assert_allclose(v[0], expect[0], atol=1e-6)

    # 模拟"模块 a/x 已写完（其向量已提交）但进程崩溃于模块 b/y 中途"：checkpoint next_row=1，
    # npy 有 3 行——第 0 行是已提交的 a/x 向量，第 1-2 行是半写垃圾
    # → embed 应先截断回 1 行（回滚半写模块）再续写，不产生重复
    write_state(state_dir, next_row=1, sha=chunks_sha(index_dir))
    (index_dir / "vectors.npy").unlink()
    np.save(index_dir / "vectors.npy",
            np.concatenate([expect[:1], np.zeros((2, 4), dtype=np.float32)]))
    fake2 = FakeEmbedder()
    st2 = embed_mod.embed(index_dir, state_dir, fake2)
    assert st2.skipped == 1 and st2.chunks_done == 2
    v2 = np.load(index_dir / "vectors.npy")
    assert v2.shape == (3, 4)
    np.testing.assert_allclose(v2[0], expect[0], atol=1e-6)  # 第 0 行未被重写：仍是已提交的 a/x 向量

    # 无改动重跑：全部 skip，npy 不变
    fake3 = FakeEmbedder()
    st3 = embed_mod.embed(index_dir, state_dir, fake3)
    assert st3.chunks_done == 0 and st3.skipped == 3
    np.testing.assert_array_equal(np.load(index_dir / "vectors.npy"), v2)


def test_embed_stale_index_guard(tmp_path):
    index_dir, state_dir = build_index(tmp_path, {"a/x": ("1.0.0", ["t"])})
    write_state(state_dir, next_row=0, sha="deadbeef")  # 与现库不符
    with pytest.raises(embed_mod.StaleIndexError):
        embed_mod.embed(index_dir, state_dir, FakeEmbedder())


def test_embed_rebuilds_npy_when_missing_despite_checkpoint(tmp_path):
    mods = {"a/x": ("1.0.0", ["ax"]), "b/y": ("2.0.0", ["by1", "by2"])}
    index_dir, state_dir = build_index(tmp_path, mods)

    # checkpoint 声称已提交 3 行，但 vectors.npy 不存在：索引不一致，
    # embed 不得信任 checkpoint —— 必须全量重建 npy（安全且收敛的方向）
    write_state(state_dir, next_row=3, sha=chunks_sha(index_dir))

    fake = FakeEmbedder()
    st = embed_mod.embed(index_dir, state_dir, fake)
    assert st.chunks_done == 3 and st.skipped == 0  # 不是全部 skip
    v = np.load(index_dir / "vectors.npy")
    assert v.shape == (3, 4)
    np.testing.assert_allclose(v, FakeEmbedder().embed(["ax", "by1", "by2"]), atol=1e-6)
    state_after = json.loads((state_dir / "index_state.json").read_text())
    assert state_after["next_row"] == 3
    assert set(state_after["modules"]) == {"a/x", "b/y"}


def test_embed_rejects_negative_checkpoint(tmp_path):
    index_dir, state_dir = build_index(tmp_path, {"a/x": ("1.0.0", ["ax"])})
    write_state(state_dir, next_row=-1, sha=chunks_sha(index_dir))
    with pytest.raises(embed_mod.StaleIndexError):
        embed_mod.embed(index_dir, state_dir, FakeEmbedder())


def test_embed_trusts_short_npy_and_rebuilds_the_rest(tmp_path):
    mods = {"a/x": ("1.0.0", ["ax"]), "b/y": ("2.0.0", ["by1", "by2"])}
    index_dir, state_dir = build_index(tmp_path, mods)

    fake = FakeEmbedder()
    st = embed_mod.embed(index_dir, state_dir, fake)
    assert st.chunks_done == 3

    # 模拟崩溃使 npy 比 checkpoint 声称的行数短：embed 必须保留已提交前缀、只重建缺失行
    np.save(index_dir / "vectors.npy", np.load(index_dir / "vectors.npy")[:1])
    fake2 = FakeEmbedder()
    st2 = embed_mod.embed(index_dir, state_dir, fake2)
    assert st2.skipped == 1 and st2.chunks_done == 2
    v2 = np.load(index_dir / "vectors.npy")
    assert v2.shape == (3, 4)
    np.testing.assert_allclose(v2, FakeEmbedder().embed(["ax", "by1", "by2"]), atol=1e-6)
    # 第 0 行（已提交前缀）未被重写：仍与 a/x 提交向量一致（容差内）
    np.testing.assert_allclose(v2[0], FakeEmbedder().embed(["ax"])[0], atol=1e-6)


def test_main_embed_offline(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("ZHIPUAI_API_KEY", raising=False)
    index_dir, state_dir = build_index(tmp_path, {"a/x": ("1.0.0", ["ax"])})
    real = api_mod.GlmEmbedder
    monkeypatch.setattr(api_mod, "GlmEmbedder", FakeEmbedder)
    embed_mod.main(["--index", str(index_dir), "--state", str(state_dir)])
    assert "EmbedStats(modules_done=1, chunks_done=1, skipped=0)" in capsys.readouterr().out
    assert np.load(index_dir / "vectors.npy").shape == (1, 4)
    monkeypatch.setattr(api_mod, "GlmEmbedder", real)
    with pytest.raises(MissingKeyError, match="ZHIPUAI_API_KEY"):
        embed_mod.main(["--index", str(index_dir), "--state", str(state_dir)])
