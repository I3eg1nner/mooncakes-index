# mooncake-mcp 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把语义检索暴露为 MCP 服务器（`search_modules` + `get_module` 双工具，stdio 与 Streamable-HTTP 双 transport），供 LLM/agent 调用找包并获取判断依据。

**Architecture:** 新增 `indexer/detail.py`（四源装配单包判断载荷的纯函数）与 `indexer/mcp_server.py`（FastMCP 实例 + 两工具 + 入口）；`search()` 的 description 字段顺手修正为 registry 优先。错误全部结构化为 LLM 可读 JSON。

**Tech Stack:** Python 3.10+，官方 `mcp` SDK 1.30.0（FastMCP，仓库首个第三方依赖，用户裁定例外；已实测安装：`FastMCP.run(transport: Literal["stdio","sse","streamable-http"])`、`@mcp.tool()`、in-memory 测试助手 `mcp.shared.memory.create_connected_server_and_client_session(server, raise_exceptions=True)`、工具返回 `CallToolResult(content[0].text, structuredContent, isError)`）。

**Spec:** `docs/superpowers/specs/2026-09-17-mooncake-mcp-design.md`

## Global Constraints

- 唯一新增第三方依赖：`mcp>=1.2,<2`（写入新文件 `requirements.txt`）；仓库其余部分维持 stdlib+numpy；`mcp` 仅被 `indexer/mcp_server.py` 与其测试导入
- 工具错误一律结构化 JSON（spec §4 表格逐字实现），不抛裸异常、不打印裸 traceback 到 stdout（stdio transport 的 stdout 是协议信道）
- 环境变量：`INDEXER_INDEX_DIR`(默认 `index`)、`INDEXER_RESULTS_PATH`(默认 `results/results.jsonl`)、`INDEXER_REGISTRY_PATH`(默认 `state/registry_index.json`)；key 沿用 `ZHIPUAI_API_KEY`/`API_KEY`
- get_module 纯本地读取，不依赖 GLM；不做按需重扫
- findings 字段如实映射 results.jsonl 的条目（键为 rule/severity/category/file/line/snippet/message），不截断
- 测试零网络零子进程：in-memory client + FakeEmbedder（`indexer/testing.py` 现有 helper）
- 每任务以 `python3 -m pytest indexer/ crawl/ -q` 全绿收尾后 commit；`moon test` 90/90 不受影响
- 注：`pip install mcp` 时环境会出现 mitmproxy 的 h11/typing-versions 冲突警告——与本任务无关，忽略，不尝试"修复"环境

---

### Task 1: `indexer/detail.py` — 单包判断载荷装配

**Files:**
- Create: `indexer/detail.py`
- Test: `indexer/test_detail.py`

**Interfaces:**
- Consumes: `index/chunks.db`（表 `chunks(id, module, version, chunk_type, label, text)`）、`index/packages.jsonl`、`results/results.jsonl`、`state/registry_index.json`
- Produces:
  - `build_module_detail(name: str, *, index_dir: Path, results_path: Path, registry_path: Path) -> dict`
  - 成功载荷：`{"name","version","description","keywords","repository","verdict","risk","findings":[...原始键...] ,"api_surface":[{"pkg","signatures":[...]}],"readme_summary"}`
  - 错误载荷（同一函数返回，键 `error` 区分）：`{"error":"module_not_found","suggestions":[...]}`、`{"error":"index_not_built","hint":"run: python3 -m indexer.collect && python3 -m indexer.embed"}`
  - `api_surface` 提取规则：`chunk_type='mbti'` 的块按 `label` 分组（label 为包相对路径，根包 label 为空串显示为 `"<root>"`），`signatures` = 该块 text 中以 `"pub "` 开头的行
  - `readme_summary` = packages.jsonl 中该模块 readme 字段前 1500 字符（缺失则 `None`）
  - verdict/risk/findings 来自 results.jsonl（缺失文件或模块 → verdict/risk 为 `None`、findings 为 `[]`）
  - description/keywords/repository 来自 registry 缓存（缺失则 `None`/`[]`/`None`）

- [ ] **Step 1: 写失败测试**

```python
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
```

- [ ] **Step 2: 运行确认失败**

Run: `python3 -m pytest indexer/test_detail.py -v`
Expected: FAIL（`ModuleNotFoundError: indexer.detail`）

- [ ] **Step 3: 最小实现**

```python
# indexer/detail.py
"""Assemble the per-module judgment payload for the MCP get_module tool.

Read-only, no network, no GLM: chunks.db + packages.jsonl + results.jsonl
+ the registry cache. Error conditions return a dict with an "error" key.
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
        rows = conn.execute(
            "SELECT version, chunk_type, label, text FROM chunks WHERE module = ?"
            " ORDER BY id", (name,)).fetchall()
    finally:
        conn.close()
    if not rows:
        names = _known_modules(index_dir)
        near = sorted(difflib.get_close_matches(name, names, n=MAX_SUGGESTIONS))[:MAX_SUGGESTIONS]
        return _err("module_not_found", suggestions=near)

    version = rows[0][0]
    api_surface: dict[str, list[str]] = {}
    for _, ctype, label, text in rows:
        if ctype != "mbti":
            continue
        pkg = label or "<root>"
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
```

- [ ] **Step 4: 运行确认通过**

Run: `python3 -m pytest indexer/test_detail.py -v`
Expected: PASS（4 passed）

- [ ] **Step 5: 全量回归 + Commit**

Run: `python3 -m pytest indexer/ crawl/ -q` → 全绿

```bash
git add indexer/detail.py indexer/test_detail.py
git commit -m "feat: module detail payload assembler (4-source, structured errors)"
```

---

### Task 2: `search()` description 修正 — registry 优先

**Files:**
- Modify: `indexer/search.py`（`search()` 签名 + `main()` 传参）
- Test: `indexer/test_search.py`

**Interfaces:**
- Consumes: `search.search()` 现签名；`state/registry_index.json`
- Produces:
  - `search(query, *, n=10, verdict, index_dir, results_path, embedder, registry_path: Path | None = None) -> list[Hit]`（新增仅关键字参数，默认 None = 不查 registry，行为向后兼容）
  - `registry_path` 提供且含该模块时：`Hit.description = registry.description`；否则回退现有最佳命中块文本
  - `main()` 传 `registry_path=Path(os.environ.get("INDEXER_REGISTRY_PATH", "state/registry_index.json"))`
  - CLI/Web/MCP 三处 description 均为语义摘要

- [ ] **Step 1: 写失败测试**

```python
# indexer/test_search.py 追加
import json
import sqlite3
from indexer.testing import FakeEmbedder, build_index, write_results


def test_description_prefers_registry(tmp_path):
    index_dir, state_dir = build_index(tmp_path)
    results_path = write_results(tmp_path)
    first = sqlite3.connect(index_dir / "chunks.db").execute(
        "SELECT module FROM chunks ORDER BY id LIMIT 1").fetchone()[0]
    reg = tmp_path / "registry.json"
    reg.write_text(json.dumps([{"name": first, "description": "REGISTRY DESC"}]))

    from indexer.search import search
    kw = dict(n=5, verdict=None, index_dir=index_dir,
              results_path=results_path, embedder=FakeEmbedder())

    hits = search("jmes", registry_path=reg, **kw)
    hit = next(h for h in hits if h.module == first)
    assert hit.description == "REGISTRY DESC"

    hits_none = search("jmes", registry_path=None, **kw)
    hit_none = next(h for h in hits_none if h.module == first)
    assert hit_none.description != "REGISTRY DESC"  # 回退块文本
```

- [ ] **Step 2: 运行确认失败**

Run: `python3 -m pytest indexer/test_search.py -v`
Expected: FAIL（`TypeError: unexpected keyword argument 'registry_path'`）

- [ ] **Step 3: 最小实现**

`search()` 尾部构造 Hit 前，加载 registry（提供时）：`{m["name"]: m.get("description") for m in json.loads(...)}`，异常（文件缺失/JSON 损坏）静默回退空 dict；Hit 构造处 `description = registry_desc.get(module) or <现逻辑>`。`main()` 补传参。

- [ ] **Step 4: 运行确认通过**

Run: `python3 -m pytest indexer/ crawl/ -q` → 全绿（含 Task 1）

- [ ] **Step 5: Commit**

```bash
git add indexer/search.py indexer/test_search.py
git commit -m "feat: Hit.description prefers registry description over chunk text"
```

---

### Task 3: `indexer/mcp_server.py` — FastMCP 双工具 + 双 transport

**Files:**
- Create: `requirements.txt`
- Create: `indexer/mcp_server.py`
- Test: `indexer/test_mcp_server.py`

**Interfaces:**
- Consumes: `search.search()`（含 Task 2 的 registry_path）、`detail.build_module_detail()`、`indexer/testing.py` helper、`indexer/api.GlmEmbedder`
- Produces:
  - 模块级 `create_mcp(index_dir, results_path, registry_path, embedder=None) -> FastMCP`（embedder=None 时懒构造 `GlmEmbedder()`；FakeEmbedder 注入点）
  - 工具 `search_modules(query: str, n: int = 10, verdict: str | None = None) -> str`（JSON 字符串）
  - 工具 `get_module(name: str) -> str`（JSON 字符串）
  - 错误映射（spec §4 逐字）：`ValueError → {"error":"invalid_argument","detail":...}`；`MissingKeyError → {"error":"missing_api_key",...}`；`embedder_unavailable`（RuntimeError/URLError 捕获）；`index_not_built`/`module_not_found` 由 detail 原样透传；search 侧索引缺失检测：`index_dir/chunks.db` 不存在时直接返回 index_not_built
  - 入口：`python3 -m indexer.mcp_server`（stdio）/ `--http --port 8000`（streamable-http）；`if __name__ == "__main__": main()`
- 备注：`mcp>=1.2,<2` 写入 `requirements.txt`（仅此一个依赖）

- [ ] **Step 1: 写失败测试**

```python
# indexer/test_mcp_server.py
import asyncio
import json
import threading
import urllib.request

import pytest

from indexer import mcp_server
from indexer.testing import FakeEmbedder, build_index, write_results


@pytest.fixture()
def mcp_env(tmp_path, monkeypatch):
    monkeypatch.setenv("INDEXER_INDEX_DIR", str(tmp_path / "index"))
    monkeypatch.setenv("INDEXER_RESULTS_PATH", str(tmp_path / "results.jsonl"))
    monkeypatch.setenv("INDEXER_REGISTRY_PATH", str(tmp_path / "registry.json"))
    build_index(tmp_path)  # 复用现有 helper：chunks.db + vectors.npy + registry 桩
    write_results(tmp_path)
    return tmp_path


def make_server():
    return mcp_server.create_mcp(embedder=FakeEmbedder())


def run(coro):
    return asyncio.run(coro)


def _first_module(index_dir):
    import sqlite3
    return sqlite3.connect(index_dir / "chunks.db").execute(
        "SELECT module FROM chunks ORDER BY id LIMIT 1").fetchone()[0]


def test_tools_registered(mcp_env):
    from mcp.shared.memory import create_connected_server_and_client_session

    async def go():
        async with create_connected_server_and_client_session(make_server()) as s:
            await s.initialize()
            tools = await s.list_tools()
            return {t.name for t in tools.tools}

    assert run(go()) == {"search_modules", "get_module"}


def test_search_modules_roundtrip(mcp_env):
    from mcp.shared.memory import create_connected_server_and_client_session

    async def go():
        async with create_connected_server_and_client_session(make_server()) as s:
            await s.initialize()
            return await s.call_tool("search_modules", {"query": "jmes", "n": 5})

    res = run(go())
    assert res.isError is False
    hits = json.loads(res.content[0].text)
    assert isinstance(hits, list) and hits and {"module", "version", "score"} <= set(hits[0])


def test_get_module_payload_and_error(mcp_env):
    from mcp.shared.memory import create_connected_server_and_client_session
    name = _first_module(mcp_env / "index")

    async def go(nm):
        async with create_connected_server_and_client_session(make_server()) as s:
            await s.initialize()
            return await s.call_tool("get_module", {"name": nm})

    d = json.loads(run(go(name)).content[0].text)
    assert d.get("name") == name and "api_surface" in d and "findings" in d
    miss = json.loads(run(go("no/such-module-xyz")).content[0].text)
    assert miss["error"] == "module_not_found" and len(miss["suggestions"]) <= 3


def test_search_invalid_argument(mcp_env):
    from mcp.shared.memory import create_connected_server_and_client_session

    async def go():
        async with create_connected_server_and_client_session(make_server()) as s:
            await s.initialize()
            return await s.call_tool("search_modules", {"query": "", "n": 5})

    assert json.loads(run(go()).content[0].text)["error"] == "invalid_argument"


def test_http_transport_roundtrip(mcp_env):
    """spec §7/§8.3：streamable-http 起 127.0.0.1:0 服务后 list/call 一轮。"""
    from mcp.client.session import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    mcp = make_server()
    app = mcp.streamable_http_app()
    import uvicorn
    config = uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning")
    server = uvicorn.Server(config)
    th = threading.Thread(target=server.run, daemon=True)
    th.start()
    while not server.started:
        threading.Event().wait(0.05)
    port = server.servers[0].sockets[0].getsockname()[1]

    async def go():
        async with streamablehttp_client(f"http://127.0.0.1:{port}/mcp") as (r, w, _):
            async with ClientSession(r, w) as s:
                await s.initialize()
                tools = await s.list_tools()
                res = await s.call_tool("get_module", {"name": _first_module(mcp_env / "index")})
                return {t.name for t in tools.tools}, json.loads(res.content[0].text)

    names, payload = run(go())
    assert names == {"search_modules", "get_module"}
    assert payload.get("name") == _first_module(mcp_env / "index")
    server.should_exit = True
    th.join(timeout=5)
```

（执行者注意：`create_connected_server_and_client_session` 返回 async context manager；`uvicorn` 随 `mcp` SDK 一并安装，无需新增依赖；若 `server.started` 轮询超时（>10s）改用 `asyncio` 启动或断言放宽为端口可达。）

- [ ] **Step 2: 运行确认失败**

Run: `python3 -m pytest indexer/test_mcp_server.py -v`
Expected: FAIL（`ModuleNotFoundError: indexer.mcp_server`）

- [ ] **Step 3: 最小实现**

```python
# indexer/mcp_server.py
"""MCP server exposing the semantic package index to LLM agents.

Tools: search_modules(query, n, verdict), get_module(name).
Transports: stdio (default) or streamable-http (--http --port N).
All tool errors are structured JSON strings — never bare exceptions.
"""
import argparse
import json
import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP


def _env_paths() -> tuple[Path, Path, Path]:
    return (Path(os.environ.get("INDEXER_INDEX_DIR", "index")),
            Path(os.environ.get("INDEXER_RESULTS_PATH", "results/results.jsonl")),
            Path(os.environ.get("INDEXER_REGISTRY_PATH", "state/registry_index.json")))


def create_mcp(index_dir: Path | None = None, results_path: Path | None = None,
               registry_path: Path | None = None, embedder=None) -> FastMCP:
    idx, res, reg = _env_paths()
    index_dir = index_dir or idx
    results_path = results_path or res
    registry_path = registry_path or reg

    mcp = FastMCP("mooncake-index")

    @mcp.tool()
    def search_modules(query: str, n: int = 10, verdict: str | None = None) -> str:
        """Semantic search over the mooncakes.io index. Returns a JSON list of
        {module, version, score, verdict, risk, description} candidates."""
        from indexer import api, search as search_mod
        try:
            if not (Path(index_dir) / "chunks.db").is_file():
                return json.dumps({"error": "index_not_built",
                                   "hint": "run: python3 -m indexer.collect && python3 -m indexer.embed"})
            emb = embedder or api.GlmEmbedder()
            hits = search_mod.search(query, n=n, verdict=verdict, index_dir=index_dir,
                                     results_path=results_path, embedder=emb,
                                     registry_path=registry_path)
            return json.dumps([h.__dict__ for h in hits], ensure_ascii=False)
        except ValueError as e:
            return json.dumps({"error": "invalid_argument", "detail": str(e)})
        except api.MissingKeyError:
            return json.dumps({"error": "missing_api_key",
                               "hint": "set ZHIPUAI_API_KEY or API_KEY"})
        except Exception as e:  # 网络类异常已在上游退避重试后仍失败
            return json.dumps({"error": "embedder_unavailable", "detail": repr(e)})

    @mcp.tool()
    def get_module(name: str) -> str:
        """Full judgment payload for one module: audit verdict/risk/findings,
        API surface, README summary. Local-only (no GLM needed)."""
        from indexer.detail import build_module_detail
        try:
            d = build_module_detail(name, index_dir=index_dir,
                                    results_path=results_path, registry_path=registry_path)
            return json.dumps(d, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": "detail_unavailable", "detail": repr(e)})

    return mcp


def main() -> None:
    ap = argparse.ArgumentParser(prog="indexer.mcp_server")
    ap.add_argument("--http", action="store_true", help="streamable-http transport")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()
    mcp = create_mcp()
    if args.http:
        mcp.settings.port = args.port
        mcp.run(transport="streamable-http")
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 运行确认通过**

Run: `python3 -m pytest indexer/test_mcp_server.py -v` → PASS；`python3 -m pytest indexer/ crawl/ -q` → 全绿

- [ ] **Step 5: stdio 冒烟（一次性，手动验证进程级入口）**

```bash
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"smoke","version":"0"}}}' | \
  timeout 10 python3 -m indexer.mcp_server | head -c 300
```

Expected: 输出含 `"serverInfo"` 的 initialize 响应（stderr 的 FastMCP 横幅忽略）

- [ ] **Step 6: Commit**

```bash
git add requirements.txt indexer/mcp_server.py indexer/test_mcp_server.py
git commit -m "feat: MCP server (search_modules + get_module, stdio/streamable-http)"
```

---

### Task 4: README + 接入文档 + 全量验收

**Files:**
- Modify: `README.mbt.md`（追加 "## MCP server" 一节）

**Interfaces:**
- Consumes: Task 1-3 全部产物
- Produces: 接入文档（opencode 与 Claude Desktop 的 stdio 配置片段）、验收记录

- [ ] **Step 1: README 追加 MCP 一节**

```markdown
## MCP server

Expose the semantic index to LLM agents (Model Context Protocol):

```bash
pip install -r requirements.txt
python3 -m indexer.mcp_server                 # stdio (default)
python3 -m indexer.mcp_server --http --port 8000
```

opencode (`~/.config/opencode/opencode.json`):

```json
{"mcp": {"mooncake-index": {"type": "local",
  "command": ["python3", "-m", "indexer.mcp_server"],
  "cwd": "/path/to/mooncacke", "enabled": true}}}
```

Claude Desktop (`claude_desktop_config.json`):

```json
{"mcpServers": {"mooncake-index": {"command": "python3",
  "args": ["-m", "indexer.mcp_server"], "cwd": "/path/to/mooncacke"}}}
```

Tools: `search_modules(query, n, verdict)` — semantic search with audit verdicts;
`get_module(name)` — full judgment payload (findings, API surface, README summary).
Env: `INDEXER_INDEX_DIR`, `INDEXER_RESULTS_PATH`, `INDEXER_REGISTRY_PATH`, key via
`ZHIPUAI_API_KEY`/`API_KEY` (search only; `get_module` works without a key).
```

- [ ] **Step 2: 全量回归**

Run: `python3 -m pytest indexer/ crawl/ -q` 全绿（预期 60+ passed, 1 skipped）；`moon test` 90/90

- [ ] **Step 3: Commit**

```bash
git add README.mbt.md
git commit -m "docs: MCP server usage and agent onboarding"
```

---

## 风险与备忘

- **asyncio in-memory 测试**：`create_connected_server_and_client_session` 是 async 生成器；若 pytest 无 asyncio 插件，用 `asyncio.run()` 包装 async 函数（计划测试代码已按此写）。若 SDK 版本行为差异导致 initialize 卡住，加 `read_timeout_seconds=timedelta(seconds=10)`。
- **stdio stdout 纪律**：工具与库代码绝不能向 stdout 打印（协议信道）；实现时确认 search/detail 全链路无 print（collect/embed 的 print 不在 MCP 路径上）。
- **requirements.txt 首次出现**：pip 冲突警告（mitmproxy）与本仓库无关，文档不需要提。
- **HF Spaces 部署（S2/S6）**：下一 spec；`--http` 入口已为其预留，验收（spec §8.3）仅到 in-process 测试为止。
