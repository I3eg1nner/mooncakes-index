# indexer/detail.py
"""Assemble the per-module judgment payload for the MCP get_module tool.

Read-only, no network, no GLM: chunks.db + packages.jsonl + results.jsonl
+ the registry cache. Error conditions return a dict with an "error" key.
The api_surface aggregates mbti chunks of the module and of its sub-modules
("name/..."): each sub-package is shown by its path relative to the module.
"""
import difflib
import json
import sqlite3
from pathlib import Path

README_SUMMARY_CHARS = 1500
MAX_SUGGESTIONS = 3


def _err(error: str, **extra) -> dict:
    return {"error": error, **extra}


def build_module_detail(name: str, *, index_dir: Path, results_path: Path,
                        registry_path: Path) -> dict:
    db_path = Path(index_dir) / "chunks.db"
    if not db_path.is_file():
        return _err("index_not_built",
                    hint="run: python3 -m indexer.collect && python3 -m indexer.embed")

    conn = sqlite3.connect(db_path)
    try:
        verrow = conn.execute(
            "SELECT version FROM chunks WHERE module = ? ORDER BY id LIMIT 1",
            (name,)).fetchone()
        if verrow is None:
            near = sorted(
                difflib.get_close_matches(name, _known_modules(index_dir), n=MAX_SUGGESTIONS)
            )[:MAX_SUGGESTIONS]
            return _err("module_not_found", suggestions=near)
        like = name.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        rows = conn.execute(
            "SELECT module, chunk_type, label, text FROM chunks"
            " WHERE module = ? OR module LIKE ? || '/%' ESCAPE '\\'"
            " ORDER BY id", (name, like)).fetchall()
    finally:
        conn.close()

    version = verrow[0]
    api_surface: dict[str, list[str]] = {}
    for module, ctype, label, text in rows:
        if ctype != "mbti":
            continue
        if module == name:
            pkg = label or "<root>"
        else:
            rel = module[len(name) + 1:]
            pkg = f"{rel}/{label}" if label else rel
        api_surface.setdefault(pkg, [])
        api_surface[pkg] += [ln for ln in text.splitlines() if ln.startswith("pub ")]

    readme_summary = None
    pj = Path(index_dir) / "packages.jsonl"
    if pj.is_file():
        with pj.open(encoding="utf-8", errors="replace") as f:
            for line in f:
                rec = json.loads(line)
                if rec.get("name") == name:
                    readme = rec.get("readme")
                    readme_summary = readme[:README_SUMMARY_CHARS] if readme else None
                    break

    verdict = risk = None
    findings: list = []
    if Path(results_path).is_file():
        with Path(results_path).open(encoding="utf-8", errors="replace") as f:
            for line in f:
                rec = json.loads(line)
                if rec.get("module") == name:
                    verdict, risk = rec.get("verdict"), rec.get("risk")
                    findings = rec.get("findings") or []
                    break

    description = keywords = repository = None
    if Path(registry_path).is_file():
        entries = json.loads(Path(registry_path).read_text(encoding="utf-8", errors="replace"))
        for rec in entries:
            if rec.get("name") == name:
                description = rec.get("description")
                keywords = rec.get("keywords") or []
                repository = rec.get("repository")
                break

    return {"name": name, "version": version, "description": description,
            "keywords": keywords or [], "repository": repository,
            "verdict": verdict, "risk": risk, "findings": findings,
            "api_surface": [{"pkg": p, "signatures": s} for p, s in api_surface.items()],
            "readme_summary": readme_summary}


def _known_modules(index_dir: Path) -> list[str]:
    conn = sqlite3.connect(Path(index_dir) / "chunks.db")
    try:
        return [r[0] for r in conn.execute("SELECT DISTINCT module FROM chunks")]
    finally:
        conn.close()
