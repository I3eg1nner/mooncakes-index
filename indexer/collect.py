# indexer/collect.py
import argparse
import json
import re
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from crawl.registry import fetch_module_index

README_MAX_CHARS = 8192
SECTION_SOFT_CAP = 2000
MBTI_MAX_CHARS = 4000
BOILERPLATE_MIN_MODULES = 20

_HEADING_RE = re.compile(r"^#{1,3} .*$", re.MULTILINE)


@dataclass
class CollectStats:
    modules: int
    with_readme: int
    with_mbti: int
    chunks: int


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _mbti_label(mbti_path: Path, module_dir: Path) -> str:
    relative = mbti_path.parent.relative_to(module_dir)
    return "" if relative == Path(".") else relative.as_posix()


def pick_readme(module_dir: Path) -> str | None:
    for name in ("README.md", "README.mbt.md"):
        candidate = module_dir / name
        if candidate.is_file():
            return _read_text(candidate)
    variants = sorted(p for p in module_dir.glob("README*.md") if p.is_file())
    if variants:
        return _read_text(variants[0])
    return None


def _split_long(text: str, limit: int = SECTION_SOFT_CAP) -> list[str]:
    if len(text) <= limit:
        return [text]
    mid = len(text) // 2
    nearest = None
    for brk in re.finditer(r"\n+", text):
        if brk.start() > 0 and brk.end() < len(text) and (
            nearest is None or abs(brk.start() - mid) < abs(nearest.start() - mid)
        ):
            nearest = brk
    if nearest is not None:
        left, right = text[: nearest.start()], text[nearest.end():]
        if left and right:
            return _split_long(left, limit) + _split_long(right, limit)
    half = len(text) // 2
    return _split_long(text[:half], limit) + _split_long(text[half:], limit)


def chunk_readme(text: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    headings = list(_HEADING_RE.finditer(text))
    if not headings:
        body = text.strip()
        if body:
            sections.extend(("", piece) for piece in _split_long(body))
        return sections
    preamble = text[: headings[0].start()].strip()
    if preamble:
        sections.extend(("", piece) for piece in _split_long(preamble))
    for i, heading in enumerate(headings):
        title = heading.group().lstrip("#").strip()
        end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        body = text[heading.end(): end].strip()
        if body:
            sections.extend((title, piece) for piece in _split_long(body))
    return sections


def _load_registry_index(state_dir: Path, fetch_registry: Callable[[], list[dict]] | None) -> dict[str, dict]:
    cache_path = state_dir / "registry_index.json"
    if cache_path.is_file():
        try:
            entries = json.loads(cache_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            entries = None
        else:
            return _registry_dict(entries)
    fetch = fetch_registry or fetch_module_index
    try:
        entries = fetch()
    except Exception as exc:
        print(f"warn: registry index fetch failed ({exc}); metadata left empty", file=sys.stderr)
        return {}
    state_dir.mkdir(parents=True, exist_ok=True)
    try:
        cache_path.write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")
    except OSError as exc:
        print(f"warn: could not write registry cache ({exc}); continuing without cache", file=sys.stderr)
    return _registry_dict(entries)


def _registry_dict(entries) -> dict[str, dict]:
    if not isinstance(entries, list):
        return {}
    return {
        entry["name"]: entry
        for entry in entries
        if isinstance(entry, dict) and isinstance(entry.get("name"), str)
    }


def _iter_module_dirs(corpus_dir: Path):
    for author_dir in sorted(p for p in corpus_dir.iterdir() if p.is_dir()):
        for module_dir in sorted(p for p in author_dir.iterdir() if p.is_dir()):
            if (module_dir / "moon.mod").is_file():
                yield module_dir


def collect(corpus_dir: Path, index_dir: Path, state_dir: Path, *, fetch_registry: Callable[[], list[dict]] | None = None) -> CollectStats:
    registry = _load_registry_index(state_dir, fetch_registry)
    index_dir.mkdir(parents=True, exist_ok=True)
    stats = CollectStats(0, 0, 0, 0)
    staged: list[tuple[dict, list[tuple[str, str, str, str | None, str]]]] = []
    for module_dir in _iter_module_dirs(corpus_dir):
        name = f"{module_dir.parent.name}/{module_dir.name}"
        meta = registry.get(name) or {}
        version = str(meta.get("version") or "")
        description = str(meta.get("description") or "")
        keywords = meta.get("keywords")
        if not isinstance(keywords, list):
            keywords = []
        meta_text = f"{name} {version}\n{description}\nkeywords: {', '.join(map(str, keywords))}"
        if "jq" in name.rsplit("/", 1)[-1].lower():
            meta_text += "\nAlias: JMESPath-family JSON query processor (implements the jq query language)"
        rows = [(name, version, "meta", None, meta_text)]
        readme_raw = pick_readme(module_dir)
        readme_text = ""
        if readme_raw is not None:
            stats.with_readme += 1
            readme_text = readme_raw[:README_MAX_CHARS]
            for title, body in chunk_readme(readme_text):
                rows.append((name, version, "readme", title, body))
        mbti_entries: list[dict[str, str]] = []
        for mbti_path in sorted(module_dir.rglob("pkg.generated.mbti"), key=str):
            label = _mbti_label(mbti_path, module_dir)
            text = _read_text(mbti_path)
            if len(text) > MBTI_MAX_CHARS:
                text = text[:MBTI_MAX_CHARS] + "\n… (truncated)"
            mbti_entries.append({"pkg": label, "text": text})
            rows.append((name, version, "mbti", label, text))
        if mbti_entries:
            stats.with_mbti += 1
        record = {
            "name": name,
            "version": version,
            "description": description,
            "keywords": keywords,
            "readme": readme_text,
            "mbti": mbti_entries,
        }
        staged.append((record, rows))
        stats.modules += 1
    occurrences: dict[str, set[str]] = {}
    for record, mod_rows in staged:
        for row in mod_rows:
            occurrences.setdefault(" ".join(row[4].split()), set()).add(record["name"])
    boilerplate = {
        text: modules
        for text, modules in occurrences.items()
        if len(modules) > BOILERPLATE_MIN_MODULES
    }
    conn = sqlite3.connect(index_dir / "chunks.db")
    try:
        conn.execute("DROP TABLE IF EXISTS chunks")
        conn.execute(
            "CREATE TABLE chunks("
            "id INTEGER PRIMARY KEY, "
            "module TEXT NOT NULL, "
            "version TEXT NOT NULL, "
            "chunk_type TEXT NOT NULL, "
            "label TEXT, "
            "text TEXT NOT NULL)"
        )
        conn.execute("DROP TABLE IF EXISTS boilerplate")
        conn.execute("CREATE TABLE boilerplate(text TEXT PRIMARY KEY, modules INTEGER)")
        rows: list[tuple[str, str, str, str | None, str]] = []
        with (index_dir / "packages.jsonl").open("w", encoding="utf-8") as out:
            for record, mod_rows in staged:
                for row in mod_rows:
                    if " ".join(row[4].split()) in boilerplate:
                        continue
                    rows.append(row)
                out.write(json.dumps(record, ensure_ascii=False) + "\n")
        conn.executemany(
            "INSERT INTO chunks(module, version, chunk_type, label, text) VALUES (?, ?, ?, ?, ?)",
            rows,
        )
        conn.executemany(
            "INSERT INTO boilerplate(text, modules) VALUES (?, ?)",
            [(text, len(modules)) for text, modules in sorted(boilerplate.items())],
        )
        conn.commit()
    finally:
        conn.close()
    stats.chunks = len(rows)
    print(f"readme: {stats.with_readme}/{stats.modules}, mbti: {stats.with_mbti}/{stats.modules}")
    return stats


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="python3 -m indexer.collect",
        description="Scan the corpus and rebuild index chunks.db + packages.jsonl")
    ap.add_argument("--corpus", type=Path, default=Path("corpus"))
    ap.add_argument("--out", type=Path, default=Path("index"))
    ap.add_argument("--state", type=Path, default=Path("state"))
    args = ap.parse_args(argv)
    print(collect(args.corpus, args.out, args.state))


if __name__ == "__main__":
    main()
