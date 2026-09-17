# mooncake-semantic-index 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 mooncakes.io 全量语料（~2500 模块）构建语义检索索引，提供 CLI 与本地 Web 两类查询入口，使 `query("jmes")` 能命中 `bobzhang/moonjq`（官方词法搜索为 0 结果）。

**Architecture:** 新增与 `crawl/` 平级的 Python 包 `indexer/`，四段管道：collect（扫描 `corpus/` 生成素材+切块入 SQLite）→ embed（GLM embedding-3 批量向量化，断点续跑）→ search（暴力余弦 top-N + join 审计 verdict）→ serve（stdlib HTTP 单页）。向量即 `float32 [N,1024]` 矩阵 + SQLite 文本块，无向量库依赖。

**Tech Stack:** Python 3.10+ 标准库（urllib/sqlite3/http.server/argparse/json）+ numpy；GLM embedding-3 API（`ZHIPUAI_API_KEY`）。

**Spec:** `docs/superpowers/specs/2026-09-17-mooncake-semantic-index-design.md`

## Global Constraints

- 只用标准库 + numpy（环境已有 numpy 2.2.6），不新增第三方依赖
- 不修改 `crawl/` 现有任何文件；只读复用其 `registry.fetch_module_index()` 与 `results/results.jsonl`
- 运行产物目录 `index/` 加入 `.gitignore`（与 `state/ corpus/ results/` 同级）
- embedding 维度固定 1024（embedding-3 的 `dimensions` 参数）
- 所有网络调用经 `crawl.registry.fetch_bytes` 同款限流模式（~2 req/s）+ 指数退避；429/5xx 重试，4xx 直接抛错
- 测试不联网：GLM 客户端通过 `Embedder` 协议注入 fake
- 每个任务以 `python3 -m pytest indexer/ -v` 全绿收尾后 commit

---

### Task 1: `indexer/api.py` — Embedder 协议 + GLM 客户端

**Files:**
- Create: `indexer/__init__.py`（空）
- Create: `indexer/api.py`
- Test: `indexer/test_api.py`

**Interfaces:**
- Produces:
  - `Embedder`（`Protocol`）：`embed(texts: list[str]) -> np.ndarray`，返回 float32 `[len(texts), 1024]`，已 L2 归一化
  - `MissingKeyError(RuntimeError)`
  - `GlmEmbedder(dims: int = 1024, batch_size: int = 16, rate_limit: float = 0.5)`，实现 `Embedder`；无 `ZHIPUAI_API_KEY` 时构造即抛 `MissingKeyError`
  - 模块级常量 `GLM_URL = "https://open.bigmodel.cn/api/paas/v4/embeddings"`

- [ ] **Step 1: 写失败测试**

```python
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
```

- [ ] **Step 2: 运行确认失败**

Run: `python3 -m pytest indexer/test_api.py -v`
Expected: FAIL（`ModuleNotFoundError: indexer` 或 `AttributeError`）

- [ ] **Step 3: 最小实现**

```python
# indexer/api.py
import json
import os
import time
import urllib.error
import urllib.request

import numpy as np

GLM_URL = "https://open.bigmodel.cn/api/paas/v4/embeddings"
RETRY_DELAYS = (0.5, 1.0, 2.0)


class MissingKeyError(RuntimeError):
    pass


class Embedder:
    def embed(self, texts: list[str]) -> np.ndarray:
        raise NotImplementedError


def _post(url: str, payload: dict, key: str) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
    )
    last: Exception | None = None
    for i in range(len(RETRY_DELAYS) + 1):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if not (e.code == 429 or 500 <= e.code <= 599):
                raise
            last = e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last = e
        if i < len(RETRY_DELAYS):
            time.sleep(RETRY_DELAYS[i])
    raise last


def _l2norm(v: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(v, axis=1, keepdims=True)
    return np.divide(v, norms, out=np.zeros_like(v), where=norms > 0)


class GlmEmbedder(Embedder):
    def __init__(self, dims: int = 1024, batch_size: int = 16, rate_limit: float = 0.5):
        self.key = os.environ.get("ZHIPUAI_API_KEY")
        if not self.key:
            raise MissingKeyError("set ZHIPUAI_API_KEY (https://open.bigmodel.cn)")
        self.dims, self.batch_size, self.rate_limit = dims, batch_size, rate_limit
        self._last = 0.0

    def embed(self, texts: list[str]) -> np.ndarray:
        out = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            wait = self.rate_limit - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()
            resp = _post(
                GLM_URL,
                {"model": "embedding-3", "input": batch, "dimensions": self.dims},
                self.key,
            )
            ordered = sorted(resp["data"], key=lambda d: d["index"])
            out.extend(d["embedding"] for d in ordered)
        return _l2norm(np.asarray(out, dtype=np.float32))
```

（注：请求体字段名 `dimensions` 与批量上限执行期先用 1 条文本做一次真实 smoke call 验证；若 API 实际参数名不同（如 `dimension`），只改 `_post` 的调用点一处。）

- [ ] **Step 4: 运行确认通过**

Run: `python3 -m pytest indexer/test_api.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add indexer/__init__.py indexer/api.py indexer/test_api.py
git commit -m "feat: embedder protocol + GLM embedding-3 client with retry"
```

---

### Task 2: `indexer/collect.py` — 语料扫描 + 切块

**Files:**
- Create: `indexer/collect.py`
- Test: `indexer/test_collect.py`

**Interfaces:**
- Consumes: `crawl.registry.fetch_module_index() -> list[dict]`（字段 `name/version/description/keywords`）
- Produces:
  - `collect(corpus_dir: Path, index_dir: Path, state_dir: Path) -> CollectStats`
  - `CollectStats`（dataclass）：`modules: int, with_readme: int, with_mbti: int, chunks: int`
  - `pick_readme(module_dir: Path) -> str | None`（README.md > README.mbt.md > sorted(README*.md) 首 个）
  - `chunk_readme(text: str) -> list[tuple[str, str]]`（返回 `[(section_title, body)]`；按 `^#{1,3} ` 切，单节超 2000 字符再按段落二分）
  - 产物：`index/packages.jsonl`（一模块一行）+ `index/chunks.db`（表结构见 spec §4；写入前 `DROP TABLE IF EXISTS` 全量重建）

- [ ] **Step 1: 写失败测试**

```python
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
```

- [ ] **Step 2: 运行确认失败**

Run: `python3 -m pytest indexer/test_collect.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 最小实现**

实现要点（执行者按此写全代码）：
- 目录扫描：`(corpus_dir/<author>/<module>)` 两层枚举，跳过无 `moon.mod` 的目录
- 元数据：`state_dir/registry_index.json` 存在则读缓存；否则调 `fetch_module_index()` 并写缓存；按 `name` 建 dict；缺失字段落空值
- meta 块文本：`f"{name} {version}\n{description}\nkeywords: {', '.join(keywords)}"`
- readme：`pick_readme` 优先级读全文，UTF-8 `errors="replace"`，截 8192 字符
- mbti：`module_dir.rglob("pkg.generated.mbti")`，`label = str(p.parent.relative_to(module_dir))`
- `packages.jsonl` 行：`{"name", "version", "description", "keywords", "readme", "mbti": [{"pkg", "text"}]}`
- chunks 依序（meta → readme 各节 → 各 mbti）写 SQLite，`id` 自增
- 结尾打印 `readme: X/Y, mbti: Z/Y` 覆盖率

- [ ] **Step 4: 运行确认通过**

Run: `python3 -m pytest indexer/test_collect.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add indexer/collect.py indexer/test_collect.py
git commit -m "feat: corpus collect + chunking into packages.jsonl and chunks.db"
```

---

### Task 3: `indexer/embed.py` — 批量向量化 + 断点续跑

**Files:**
- Create: `indexer/embed.py`
- Test: `indexer/test_embed.py`

**Interfaces:**
- Consumes: `api.Embedder`（Task 1）、`index/chunks.db`
- Produces:
  - `embed(index_dir: Path, state_dir: Path, embedder: Embedder) -> EmbedStats`
  - `EmbedStats`（dataclass）：`modules_done: int, chunks_done: int, skipped: int`
  - `index/vectors.npy`：float32 `[N, 1024]`，行 i 对应 `chunks.id = i`，写入前已归一化
  - `state/index_state.json`：`{"chunks_sha": "<sha256 of chunks.db>", "next_row": int, "modules": {name: {"version", "chunks"}}}`

语义：
- 启动时校验 `chunks_sha`：不一致（collect 重跑过）→ 抛 `StaleIndexError`，提示删除 `index/vectors.npy` 与 `state/index_state.json` 后重跑 embed
- 崩溃恢复：读 `next_row`，若 `npy` 行数 > `next_row` 则截断回 `next_row`（回滚半写的模块），再继续
- 按 module 分组提交：一组内所有 chunk 一次 `embedder.embed(texts)`；成功后 `next_row += len(texts)` 并写 checkpoint

- [ ] **Step 1: 写失败测试**

```python
# indexer/test_embed.py
import hashlib
import json
import sqlite3
import numpy as np
import pytest
from indexer import embed as embed_mod


class FakeEmbedder:
    """确定性 fake：sha256(text) 前 4 字节归一化为向量，并记录每次调用。"""
    def __init__(self):
        self.calls = []

    def embed(self, texts):
        self.calls.append(list(texts))
        vecs = []
        for t in texts:
            raw = np.frombuffer(hashlib.sha256(t.encode()).digest()[:4], dtype=np.uint8)
            v = raw.astype(np.float32) / 255.0
            vecs.append(v / max(np.linalg.norm(v), 1e-9))
        return np.stack(vecs)


def build_index(tmp_path, modules):
    """modules: {name: (version, [chunk_texts])}；返回 (index_dir, state_dir)。"""
    index_dir = tmp_path / "index"; index_dir.mkdir()
    state_dir = tmp_path / "state"; state_dir.mkdir()
    db = sqlite3.connect(index_dir / "chunks.db")
    db.execute("CREATE TABLE chunks(id INTEGER PRIMARY KEY, module TEXT, version TEXT,"
               " chunk_type TEXT, label TEXT, text TEXT)")
    for name, (version, texts) in modules.items():
        for t in texts:
            db.execute("INSERT INTO chunks(module, version, chunk_type, label, text)"
                       " VALUES (?,?,?,?,?)", (name, version, "meta", None, t))
    db.commit(); db.close()
    return index_dir, state_dir


def write_state(state_dir, next_row, sha):
    (state_dir / "index_state.json").write_text(json.dumps(
        {"chunks_sha": sha, "next_row": next_row, "modules": {}}))


def chunks_sha(index_dir):
    return hashlib.sha256((index_dir / "chunks.db").read_bytes()).hexdigest()


def test_embed_resume_and_rollback(tmp_path):
    mods = {"a/x": ("1.0.0", ["ax"]), "b/y": ("2.0.0", ["by1", "by2"])}
    index_dir, state_dir = build_index(tmp_path, mods)

    # 无 checkpoint：全量 3 chunk
    fake = FakeEmbedder()
    st = embed_mod.embed(index_dir, state_dir, fake)
    assert st.chunks_done == 3 and st.skipped == 0
    v = np.load(index_dir / "vectors.npy")
    assert v.shape == (3, 4)
    # 行 i 与 chunks.id=i 对齐：第 0 行应可由 FakeEmbedder 重算复现
    expect = FakeEmbedder().embed(["ax"])
    np.testing.assert_allclose(v[0], expect[0], atol=1e-6)

    # 模拟"模块 a/x 已写完但进程崩溃于模块 b/y 中途"：checkpoint next_row=1，
    # npy 含 3 行（含 2 行半成品）→ embed 应先截断回 1 行再续写，不产生重复
    write_state(state_dir, next_row=1, sha=chunks_sha(index_dir))
    (index_dir / "vectors.npy").unlink()
    np.save(index_dir / "vectors.npy", np.zeros((3, 4), dtype=np.float32))
    fake2 = FakeEmbedder()
    st2 = embed_mod.embed(index_dir, state_dir, fake2)
    assert st2.skipped == 1 and st2.chunks_done == 2
    v2 = np.load(index_dir / "vectors.npy")
    assert v2.shape == (3, 4)
    np.testing.assert_allclose(v2[0], expect[0], atol=1e-6)  # 第 0 行未被重写

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
```

- [ ] **Step 2: 运行确认失败**

Run: `python3 -m pytest indexer/test_embed.py -v`
Expected: FAIL（`embed`/`StaleIndexError` 未定义）

- [ ] **Step 3: 最小实现**

按上方"语义"三条与测试断言实现：`EmbedStats`、`StaleIndexError`、`embed(index_dir, state_dir, embedder)`。要点：分组 embed（每模块一批）、成功即写 `state/index_state.json`（`chunks_sha` 校验不符抛 `StaleIndexError`）、启动时按 `next_row` 截断 `vectors.npy` 回滚半写行、向量写入前 L2 归一化、行号与 `chunks.id` 对齐。

- [ ] **Step 4: 运行确认通过**

Run: `python3 -m pytest indexer/test_embed.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add indexer/embed.py indexer/test_embed.py
git commit -m "feat: batch embedding with checkpoint resume and stale-index guard"
```

---

### Task 4: `indexer/search.py` — CLI 检索

**Files:**
- Create: `indexer/search.py`
- Test: `indexer/test_search.py`

**Interfaces:**
- Consumes: `api.Embedder`（query 向量化）、`index/vectors.npy`、`index/chunks.db`、`results/results.jsonl`
- Produces:
  - `Hit`（dataclass）：`module: str, version: str, score: float, verdict: str | None, risk: int | None, description: str`
  - `search(query: str, *, n: int = 10, verdict: str | None, index_dir: Path, results_path: Path, embedder: Embedder) -> list[Hit]`
  - 聚合：每模块取其 chunk 得分最大值
  - `load_verdicts(results_path) -> dict[str, dict]`（`module -> {"verdict","risk","version"}`）
  - CLI：`python3 -m indexer.search "jmes" -n 10 [--verdict clean] [--json]`
    - 表格输出：`score | module | verdict | description[:70]`；`--json` 输出 `[hit.__dict__]`
  - verdict 过滤在 join 之后做，`--verdict clean` 只留 `verdict == "Clean"`（大小写不敏感）

- [ ] **Step 1: 写失败测试**

```python
# indexer/test_search.py
import json
import numpy as np
from indexer.search import search, load_verdicts


def test_load_verdicts_missing_and_present(tmp_path):
    f = tmp_path / "results.jsonl"
    f.write_text(json.dumps({"module": "a/b", "version": "1.0.0", "verdict": "Clean", "risk": 0}) + "\n")
    v = load_verdicts(f)
    assert v["a/b"]["verdict"] == "Clean"
    assert v.get("x/y") is None


def test_search_ranks_expected_module_top(tmp_path):
    # fixture：2 模块 × 1 chunk；FakeEmbedder 使 query 向量 = "moonjq" chunk 向量
    index_dir, state_dir = build_index(tmp_path, {
        "bobzhang/moonjq": ("0.1.2", ["jq jmespath json query"]),
        "evil/pwn": ("9.9.9", ["malicious payload"]),
    })
    np.save(index_dir / "vectors.npy", FakeEmbedder().embed(
        ["jq jmespath json query", "malicious payload"]))

    class QueryIsJq(FakeEmbedder):
        def embed(self, texts):
            return FakeEmbedder().embed(["jq jmespath json query"])  # query≈moonjq chunk

    hits = search.search("jmes", n=5, verdict=None, index_dir=index_dir,
                         results_path=tmp_path / "results.jsonl", embedder=QueryIsJq())
    assert hits[0].module == "bobzhang/moonjq" and hits[0].score == pytest.approx(1.0, abs=1e-6)


def test_search_empty_query_raises(tmp_path):
    with pytest.raises(ValueError):
        search.search("", n=5, verdict=None, index_dir=tmp_path,
                      results_path=tmp_path / "r.jsonl", embedder=FakeEmbedder())


def test_search_verdict_filter(tmp_path):
    # evil/pwn 标记 Malicious → --verdict clean 后结果只剩 moonjq
    (tmp_path / "results.jsonl").write_text(json.dumps(
        {"module": "evil/pwn", "version": "9.9.9", "verdict": "Malicious", "risk": 9}) + "\n")
    hits = search.search("jmes", n=5, verdict="clean", index_dir=..., 
                         results_path=tmp_path / "results.jsonl", embedder=FakeEmbedder())
    assert all(h.verdict != "Malicious" for h in hits)
```

（fixture 复用 Task 3 的 `build_index`/`FakeEmbedder` helper——实现时把二者提取到 `indexer/testing.py` 供 test_search/test_serve/test_golden 共用。）

- [ ] **Step 2: 运行确认失败**

Run: `python3 -m pytest indexer/test_search.py -v`
Expected: FAIL

- [ ] **Step 3: 最小实现**

实现 `Hit`、`load_verdicts`、`search`、`main`。要点：query 空/超长（>512 字符）抛 `ValueError`；verdict 过滤大小写不敏感且在 join 之后；每模块得分取其 chunk 最大值；`results.jsonl` 缺失模块时 verdict/risk 为 `None`。

- [ ] **Step 4: 运行确认通过**

Run: `python3 -m pytest indexer/test_search.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add indexer/search.py indexer/test_search.py
git commit -m "feat: semantic search CLI with verdict join"
```

---

### Task 5: `indexer/serve.py` — 本地 Web

**Files:**
- Create: `indexer/serve.py`
- Test: `indexer/test_serve.py`

**Interfaces:**
- Consumes: `search.search`（Task 4，同一签名）
- Produces:
  - `make_handler(index_dir, results_path, embedder) -> BaseHTTPRequestHandler` 工厂
  - `serve(port: int = 8765, ..., open_browser: bool = False) -> None`（阻塞；`open_browser=True` 时 `webbrowser.open`）
  - `GET /` → `200 text/html`（内嵌常量 `PAGE_HTML`：搜索框 + 结果卡片，卡片含包名/分数/verdict 徽章/描述；JS fetch `/api/search`）
  - `GET /api/search?q=<str>&n=<int>&verdict=<str>` → `200 application/json`，body = `[hit.__dict__]`，与 CLI `--json` 完全同构；缺 `q` → 400
  - CLI：`python3 -m indexer.serve [--port 8765] [--open]`

- [ ] **Step 1: 写失败测试**

```python
# indexer/test_serve.py
import json
import threading
import urllib.error
import urllib.request
from http.server import HTTPServer

from indexer import search as search_mod
from indexer.serve import make_handler
from indexer.testing import FakeEmbedder, build_index, write_results  # Task 3/4 提取的公共 helper


def test_api_search_same_shape_as_cli(tmp_path):
    index_dir = build_index(tmp_path)
    results_path = write_results(tmp_path)
    srv = HTTPServer(("127.0.0.1", 0),
                     make_handler(index_dir, results_path, FakeEmbedder()))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"

    # /api/search 与 CLI --json 同构
    want = [h.__dict__ for h in search_mod.search(
        "jmes", n=5, verdict=None, index_dir=index_dir,
        results_path=results_path, embedder=FakeEmbedder())]
    got = json.load(urllib.request.urlopen(f"{base}/api/search?q=jmes&n=5"))
    assert got == want

    # / 返回 HTML 页；缺 q 返回 400
    with urllib.request.urlopen(f"{base}/") as r:
        assert r.headers["Content-Type"].startswith("text/html")
    try:
        urllib.request.urlopen(f"{base}/api/search")
        assert False, "expected 400"
    except urllib.error.HTTPError as e:
        assert e.code == 400
    srv.shutdown()
```

（`indexer/testing.py` 在 Task 3 首次需要时创建，Task 4/5 复用：`FakeEmbedder`、`build_index(tmp_path)`（写 chunks.db + vectors.npy + registry 缓存桩）、`write_results(tmp_path)`（写 results.jsonl 桩）。Task 3 原有测试可继续用其局部 fixture，提取动作在 Task 4 Step 3 一并完成。）

- [ ] **Step 2: 运行确认失败**

Run: `python3 -m pytest indexer/test_serve.py -v`
Expected: FAIL

- [ ] **Step 3: 最小实现**

`make_handler` + `PAGE_HTML` + `main`（argparse：`--port/--open`）。

- [ ] **Step 4: 运行确认通过**

Run: `python3 -m pytest indexer/test_serve.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add indexer/serve.py indexer/test_serve.py
git commit -m "feat: local web UI for semantic search (stdlib http.server)"
```

---

### Task 6: 真实语料端到端 + 黄金用例 + 收尾

**Files:**
- Modify: `.gitignore`（追加 `index/`）
- Modify: `README.mbt.md`（新增 "## Semantic index" 一节：build → collect → embed → search/serve 四条命令）
- Test: `indexer/test_golden.py`

**Interfaces:**
- Consumes: Task 2/3/4 全部产物
- Produces:
  - 集成测试 `test_golden_jmes`：用真实 GLM API（skipif 无 `ZHIPUAI_API_KEY`）对真实语料检索 `"jmes"`，断言 `bobzhang/moonjq` ∈ top-5
  - 冒烟验证命令记录进 README

- [ ] **Step 1: 写集成测试（skipif 无 key）**

```python
# indexer/test_golden.py
import os
import pytest
from indexer import api, collect, embed, search

pytestmark = pytest.mark.skipif(
    not os.environ.get("ZHIPUAI_API_KEY"), reason="needs ZHIPUAI_API_KEY")


def test_golden_jmes(tmp_path):
    collect(Path("corpus"), tmp_path / "index", Path("state"))
    embed(tmp_path / "index", Path("state"), api.GlmEmbedder())
    hits = search.search("jmes", n=5, verdict=None,
                         index_dir=tmp_path / "index",
                         results_path=Path("results/results.jsonl"),
                         embedder=api.GlmEmbedder())
    assert "bobzhang/moonjq" in {h.module for h in hits}
```

- [ ] **Step 2: 全量构建 + 黄金用例真跑一次**

```bash
python3 -m indexer.collect
python3 -m indexer.embed          # 记录耗时与 chunk 总数
python3 -m pytest indexer/test_golden.py -v
python3 -m indexer.search "jmes" -n 5    # 人工确认 moonjq 在列
```

Expected: golden test PASS；若 top-5 未命中 → 回到 Task 2 调整 meta 块文本（补一行 "alias: JMESPath-style JSON query language" 由 description 推导——不硬编码包名，规则：name 含 jq/jmes 类词根时追加说明），重跑 collect+embed。

- [ ] **Step 3: `.gitignore` + README**

- [ ] **Step 4: 全量回归**

```bash
python3 -m pytest indexer/ crawl/ -v && moon test
```

Expected: 全绿

- [ ] **Step 5: Commit**

```bash
git add .gitignore README.mbt.md indexer/test_golden.py
git commit -m "feat: golden jmes->moonjq e2e case, docs, gitignore index artifacts"
```

---

## 风险与备忘

- **GLM API 形状**：`dimensions` 参数名/批量上限执行期以一次真实 smoke call 为准（Task 1 Step 3 注释已留集中改名点）；批量默认 16、限流 0.5s 保守起步。
- **README 优先级**：spec 定的是 `README.md > README.mbt.md`；若实数据发现 `.mbt.md` 普遍信息量更大，属实现期可调参数（collect 内单点常量）。
- **collect 重建语义**：collect 永远全量重建 `chunks.db` 并使旧 `vectors.npy/index_state.json` 失效（sha 守卫在 Task 3）。刷新语料 = 重跑 crawl → collect → embed。
- **不做**：向量库、`moon info` 补签名、增量抓取、发布到 mooncakes。
