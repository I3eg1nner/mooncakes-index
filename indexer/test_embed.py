# indexer/test_embed.py
import sqlite3

import numpy as np
import pytest

from indexer import api as api_mod
from indexer import embed as embed_mod
from indexer.api import MissingKeyError
from indexer.testing import FakeEmbedder, build_index, rewrite_chunks

MODS = {"a/x": ("1.0.0", ["ax"]), "b/y": ("2.0.0", ["by1", "by2"])}


def test_embed_full_then_idempotent(tmp_path):
    index_dir, state_dir = build_index(tmp_path, MODS)
    fake = FakeEmbedder()
    st = embed_mod.embed(index_dir, state_dir, fake)
    assert st.embedded == 3 and st.reused == 0
    v = np.load(index_dir / "vectors.npy")
    assert v.shape == (3, 4)
    np.testing.assert_allclose(v[0], FakeEmbedder().embed(["ax"])[0], atol=1e-6)

    # 重跑：全部复用，npy 一字不变
    fake2 = FakeEmbedder()
    st2 = embed_mod.embed(index_dir, state_dir, fake2)
    assert st2.embedded == 0 and st2.reused == 3
    assert fake2.calls == []
    np.testing.assert_array_equal(np.load(index_dir / "vectors.npy"), v)


def test_embed_incremental_new_module(tmp_path):
    index_dir, state_dir = build_index(tmp_path, MODS)
    embed_mod.embed(index_dir, state_dir, FakeEmbedder())
    old = np.load(index_dir / "vectors.npy")

    # 模拟 collect 重建：新增 c/z，旧 hash 保持不变
    rewrite_chunks(index_dir, {**MODS, "c/z": ("3.0.0", ["cz"])})
    fake = FakeEmbedder()
    st = embed_mod.embed(index_dir, state_dir, fake)
    assert st.embedded == 1 and st.reused == 3
    assert fake.calls == [["cz"]]  # 只嵌入新块
    new = np.load(index_dir / "vectors.npy")
    np.testing.assert_array_equal(new[:3], old)  # 旧行原样
    np.testing.assert_allclose(new[3], fake.embed(["cz"])[0], atol=1e-6)


def test_embed_modified_chunk_reembeds_only_it(tmp_path):
    index_dir, state_dir = build_index(tmp_path, MODS)
    embed_mod.embed(index_dir, state_dir, FakeEmbedder())

    # b/y 的 README 改版：b/y@2.0.0 → 2.1.0，块文本不变但 version 变 → hash 变
    changed = {"a/x": ("1.0.0", ["ax"]), "b/y": ("2.1.0", ["by1", "by2"])}
    rewrite_chunks(index_dir, changed)
    fake = FakeEmbedder()
    st = embed_mod.embed(index_dir, state_dir, fake)
    assert st.embedded == 2 and st.reused == 1  # 只有 b/y 的两块
    assert sorted(fake.calls[0]) == ["by1", "by2"]
    assert st.dead_rows == 2  # 旧 b/y 两行成死行（未到压缩阈值）


def test_embed_orphan_tail_tolerated(tmp_path):
    index_dir, state_dir = build_index(tmp_path, MODS)
    embed_mod.embed(index_dir, state_dir, FakeEmbedder())
    # 模拟崩溃残留：npy 尾部多出未登记的垃圾行
    v = np.load(index_dir / "vectors.npy")
    np.save(index_dir / "vectors.npy",
            np.concatenate([v, np.zeros((2, 4), dtype=np.float32)]))

    rewrite_chunks(index_dir, {**MODS, "c/z": ("3.0.0", ["cz"])})
    st = embed_mod.embed(index_dir, state_dir, FakeEmbedder())
    assert st.embedded == 1
    new = np.load(index_dir / "vectors.npy")
    assert new.shape == (6, 4)  # 3 已提交 + 2 垃圾 + 1 新
    # 登记行指向正确：c/z 的向量在最后一行
    conn = sqlite3.connect(index_dir / "chunks.db")
    row = conn.execute(
        "SELECT v.row FROM vecrows v JOIN chunks c ON c.chunk_hash=v.chunk_hash"
        " WHERE c.module='c/z'").fetchone()[0]
    conn.close()
    assert row == 5


def test_embed_missing_npy_rebuilds(tmp_path):
    index_dir, state_dir = build_index(tmp_path, MODS)
    embed_mod.embed(index_dir, state_dir, FakeEmbedder())
    (index_dir / "vectors.npy").unlink()

    st = embed_mod.embed(index_dir, state_dir, FakeEmbedder())
    assert st.embedded == 3 and st.reused == 0  # 映射随 npy 一并作废
    assert np.load(index_dir / "vectors.npy").shape == (3, 4)


def test_embed_compaction_removes_dead(tmp_path):
    index_dir, state_dir = build_index(tmp_path, MODS)
    embed_mod.embed(index_dir, state_dir, FakeEmbedder())

    # b/y 整个模块下线 → 两行死行；压低阈值触发压缩
    rewrite_chunks(index_dir, {"a/x": ("1.0.0", ["ax"])})
    st = embed_mod.embed(index_dir, state_dir, FakeEmbedder(),
                         compact_min_dead=1, compact_dead_fraction=0.0)
    assert st.compacted == 2 and st.dead_rows == 0
    new = np.load(index_dir / "vectors.npy")
    assert new.shape == (1, 4)  # 只留活行
    # 剩余映射重排到 0
    conn = sqlite3.connect(index_dir / "chunks.db")
    assert conn.execute("SELECT row FROM vecrows").fetchone()[0] == 0
    conn.close()
    # 搜索仍可用（旧向量被保留）
    from indexer.search import search
    hits = search("jq", n=5, verdict=None, index_dir=index_dir,
                  results_path=tmp_path / "none.jsonl", embedder=FakeEmbedder())
    assert {h.module for h in hits} == {"a/x"}


def test_embed_migrates_legacy_schema(tmp_path):
    # 手工构造旧版（无 chunk_hash、id 对齐）数据库
    index_dir = tmp_path / "index"
    index_dir.mkdir()
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    conn = sqlite3.connect(index_dir / "chunks.db")
    conn.execute("CREATE TABLE chunks(id INTEGER PRIMARY KEY, module TEXT,"
                 " version TEXT, chunk_type TEXT, label TEXT, text TEXT)")
    texts = ["ax", "by1", "by2"]
    for name, chunk in (("a/x", "ax"), ("b/y", "by1"), ("b/y", "by2")):
        conn.execute("INSERT INTO chunks(module, version, chunk_type, label, text)"
                     " VALUES (?,?,?,?,?)", (name, "1.0.0", "meta", None, chunk))
    conn.commit()
    conn.close()
    np.save(index_dir / "vectors.npy", FakeEmbedder().embed(texts))
    (state_dir / "index_state.json").write_text(
        '{"chunks_sha": "irrelevant", "next_row": 3, "modules": {}}')

    st = embed_mod.embed(index_dir, state_dir, FakeEmbedder())
    assert st.embedded == 0 and st.reused == 3  # 迁移后向量全部复用
    conn = sqlite3.connect(index_dir / "chunks.db")
    assert embed_mod._has_column(conn, "chunks", "chunk_hash")
    assert conn.execute("SELECT COUNT(*) FROM vecrows").fetchone()[0] == 3
    conn.close()


def test_main_embed_offline(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("ZHIPUAI_API_KEY", raising=False)
    index_dir, state_dir = build_index(tmp_path, {"a/x": ("1.0.0", ["ax"])})
    real = api_mod.GlmEmbedder
    monkeypatch.setattr(api_mod, "GlmEmbedder", FakeEmbedder)
    embed_mod.main(["--index", str(index_dir), "--state", str(state_dir)])
    assert "EmbedStats(embedded=1, reused=0" in capsys.readouterr().out
    assert np.load(index_dir / "vectors.npy").shape == (1, 4)
    monkeypatch.setattr(api_mod, "GlmEmbedder", real)
    with pytest.raises(MissingKeyError, match="ZHIPUAI_API_KEY"):
        embed_mod.main(["--index", str(index_dir), "--state", str(state_dir)])
