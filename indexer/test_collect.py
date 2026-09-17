# indexer/test_collect.py
import sqlite3
from pathlib import Path

from indexer import collect as collect_mod
from indexer.collect import collect, pick_readme, chunk_readme


def make_pkg(root: Path, name: str, version: str, readme: str | None, mbtis: dict[str, str]):
    d = root / name
    d.mkdir(parents=True)
    (d / "moon.mod").write_text(f'{{"name":"{name}","version":"{version}"}}')
    if readme:
        (d / "README.md").write_text(readme)
    for pkg, text in mbtis.items():
        p = d / pkg
        p.mkdir(parents=True, exist_ok=True)
        (p / "pkg.generated.mbti").write_text(text)


def test_pick_readme_priority(tmp_path):
    (tmp_path / "README.mbt.md").write_text("b")
    (tmp_path / "README.md").write_text("a")
    assert pick_readme(tmp_path) == "a"


def test_chunk_readme_sections_and_cap():
    text = "# T1\n" + "x" * 3000 + "\n\n# T2\nshort"
    chunks = chunk_readme(text)
    assert [c[0] for c in chunks] == ["T1", "T1", "T2"]  # 超长节被二分
    assert all(len(c[1]) <= 2100 for c in chunks)


def test_collect_end_to_end(tmp_path):
    corpus = tmp_path / "corpus"
    make_pkg(corpus, "bobzhang/moonjq", "0.1.2", "# moonjq\nA jq implementation", {"": "fn query(...)"})
    make_pkg(corpus, "empty/noreadme", "0.1.0", None, {})
    stats = collect(corpus, tmp_path / "index", tmp_path, fetch_registry=lambda: [])
    assert stats.modules == 2 and stats.with_readme == 1 and stats.with_mbti == 1
    rows = sqlite3.connect(tmp_path / "index/chunks.db").execute(
        "SELECT module, chunk_type FROM chunks ORDER BY id").fetchall()
    assert ("bobzhang/moonjq", "meta") in rows and ("bobzhang/moonjq", "mbti") in rows
    assert not any(m == "empty/noreadme" and t != "meta" for m, t in rows)


def test_main_collect_offline(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("ZHIPUAI_API_KEY", raising=False)
    make_pkg(tmp_path / "corpus", "bobzhang/moonjq", "0.1.2",
             "# moonjq\nA jq implementation", {"": "fn query(...)"})
    state = tmp_path / "state"
    state.mkdir()
    (state / "registry_index.json").write_text(
        '[{"name": "bobzhang/moonjq", "version": "0.1.2", "description": "jq", "keywords": []}]',
        encoding="utf-8")
    collect_mod.main(["--corpus", str(tmp_path / "corpus"),
                      "--out", str(tmp_path / "index"), "--state", str(state)])
    out = capsys.readouterr().out
    assert "readme: 1/1, mbti: 1/1" in out
    assert "CollectStats(modules=1, with_readme=1, with_mbti=1, chunks=3)" in out
    assert (tmp_path / "index" / "chunks.db").is_file()
    assert (tmp_path / "index" / "packages.jsonl").is_file()
