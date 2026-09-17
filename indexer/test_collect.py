# indexer/test_collect.py
import json
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


def test_boilerplate_chunks_demoted(tmp_path, monkeypatch):
    monkeypatch.setattr(collect_mod, "BOILERPLATE_MIN_MODULES", 2)
    corpus = tmp_path / "corpus"
    shared = "# Shared\n" + ("same boilerplate line\n" * 30)
    make_pkg(corpus, "a/m1", "0.1.0", shared, {})
    make_pkg(corpus, "a/m2", "0.2.0", shared, {})
    make_pkg(corpus, "b/m3", "0.3.0", shared, {})
    make_pkg(corpus, "b/u1", "0.4.0", "# U1\nunique text one", {})
    make_pkg(corpus, "b/u2", "0.5.0", "# U2\nunique text two", {})
    stats = collect(corpus, tmp_path / "index", tmp_path, fetch_registry=lambda: [])
    assert stats.modules == 5 and stats.with_readme == 5
    conn = sqlite3.connect(tmp_path / "index/chunks.db")
    assert conn.execute(
        "SELECT COUNT(*) FROM chunks WHERE text LIKE '%same boilerplate line%'").fetchone()[0] == 0
    demoted = conn.execute("SELECT text, modules FROM boilerplate").fetchall()
    assert len(demoted) == 1 and demoted[0][1] == 3
    assert "same boilerplate line" in demoted[0][0]
    assert conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0] == 7
    records = {json.loads(line)["name"]: json.loads(line)
               for line in (tmp_path / "index" / "packages.jsonl").read_text(encoding="utf-8").splitlines()}
    for mod in ("a/m1", "a/m2", "b/m3"):
        assert "same boilerplate line" in records[mod]["readme"]


def test_jq_family_meta_alias(tmp_path):
    corpus = tmp_path / "corpus"
    make_pkg(corpus, "x/jq", "1.0.0", None, {})
    collect(corpus, tmp_path / "index", tmp_path, fetch_registry=lambda: [])
    row = sqlite3.connect(tmp_path / "index/chunks.db").execute(
        "SELECT text FROM chunks WHERE chunk_type = 'meta'").fetchone()
    assert row is not None and "Alias: JMESPath-family" in row[0]
