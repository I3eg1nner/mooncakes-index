# indexer/test_detail.py
import json
import sqlite3
from indexer.detail import build_module_detail


def make_fixtures(tmp_path, modules, results=None, registry=None, readmes=None):
    """modules: {name: (version, mbti: {pkg: text})}; 其余可选。"""
    index_dir = tmp_path / "index"; index_dir.mkdir()
    db = sqlite3.connect(index_dir / "chunks.db")
    db.execute("CREATE TABLE chunks(id INTEGER PRIMARY KEY, module TEXT, version TEXT,"
               " chunk_type TEXT, label TEXT, text TEXT)")
    pkgs = []
    for name, (version, mbtis) in modules.items():
        db.execute("INSERT INTO chunks(module, version, chunk_type, label, text)"
                   " VALUES (?,?,?,?,?)", (name, version, "meta", None, name))
        for pkg, text in mbtis.items():
            db.execute("INSERT INTO chunks(module, version, chunk_type, label, text)"
                       " VALUES (?,?,?,?,?)", (name, version, "mbti", pkg, text))
    db.commit(); db.close()
    pj = index_dir / "packages.jsonl"
    with pj.open("w") as f:
        for name in modules:
            f.write(json.dumps({"name": name, "readme": (readmes or {}).get(name)}) + "\n")
    rp = tmp_path / "results.jsonl"
    with rp.open("w") as f:
        for r in (results or []):
            f.write(json.dumps(r) + "\n")
    reg = tmp_path / "registry.json"
    reg.write_text(json.dumps(registry or []))
    return index_dir, rp, reg


def test_full_payload(tmp_path):
    index_dir, rp, reg = make_fixtures(
        tmp_path,
        {"bobzhang/moonjq": ("0.1.2", {"": "package jq\npub fn query(s: String) -> String\nfn helper()"}),
         "bobzhang/moonjq/cmd/jq": ("0.1.2", {"": "pub fn main()"})},
        results=[{"module": "bobzhang/moonjq", "version": "0.1.2", "verdict": "Clean",
                  "risk": 0, "findings": []}],
        registry=[{"name": "bobzhang/moonjq", "description": "A jq implementation",
                   "keywords": ["jq"], "repository": "https://github.com/x"}],
        readmes={"bobzhang/moonjq": "R" * 2000})
    d = build_module_detail("bobzhang/moonjq", index_dir=index_dir, results_path=rp, registry_path=reg)
    assert d["verdict"] == "Clean" and d["risk"] == 0 and d["findings"] == []
    assert d["description"] == "A jq implementation" and d["repository"] == "https://github.com/x"
    assert d["readme_summary"] == "R" * 1500 and len(d["readme_summary"]) == 1500
    surf = {a["pkg"]: a["signatures"] for a in d["api_surface"]}
    assert surf["<root>"] == ["pub fn query(s: String) -> String"]
    assert surf["cmd/jq"] == ["pub fn main()"]


def test_module_not_found_with_suggestions(tmp_path):
    index_dir, rp, reg = make_fixtures(tmp_path, {"bobzhang/moonjq": ("0.1.2", {})})
    d = build_module_detail("bobzhang/moonjq2", index_dir=index_dir, results_path=rp, registry_path=reg)
    assert d["error"] == "module_not_found"
    assert any("moonjq" in s for s in d["suggestions"]) and len(d["suggestions"]) <= 3


def test_missing_results_and_readme_and_registry(tmp_path):
    index_dir, rp, reg = make_fixtures(tmp_path, {"a/b": ("1.0.0", {})})
    d = build_module_detail("a/b", index_dir=index_dir, results_path=tmp_path / "nope.jsonl",
                            registry_path=tmp_path / "nope.json")
    assert d["verdict"] is None and d["findings"] == [] and d["readme_summary"] is None
    assert d["description"] is None and d["keywords"] == []


def test_index_not_built(tmp_path):
    d = build_module_detail("a/b", index_dir=tmp_path / "noindex",
                            results_path=tmp_path / "r.jsonl", registry_path=tmp_path / "g.json")
    assert d["error"] == "index_not_built"
