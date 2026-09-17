# indexer/test_collect.py
import sqlite3
from pathlib import Path

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
    stats = collect(corpus, tmp_path / "index", tmp_path)
    assert stats.modules == 2 and stats.with_readme == 1 and stats.with_mbti == 1
    rows = sqlite3.connect(tmp_path / "index/chunks.db").execute(
        "SELECT module, chunk_type FROM chunks ORDER BY id").fetchall()
    assert ("bobzhang/moonjq", "meta") in rows and ("bobzhang/moonjq", "mbti") in rows
    assert not any(m == "empty/noreadme" and t != "meta" for m, t in rows)
