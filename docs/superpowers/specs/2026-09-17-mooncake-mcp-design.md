# mooncake-mcp 设计文档

日期：2026-09-17
状态：已获用户批准

## 1. 目标与范围

把语义检索能力暴露为 **MCP（Model Context Protocol）服务器**，让大模型/agent 能调用两个工具完成"找包 + 拿判断依据"：

- **`search_modules(query, n=10, verdict=None)`** — 语义检索，返回带 verdict/risk 的候选包列表
- **`get_module(name)`** — 单包判断载荷：审计结果（verdict/risk/findings）+ 元数据 + API 面 + README 摘要

**部署路线（用户裁定）**：S2+S6 合体 —— 后续在 HF Spaces 免费层部署 FastAPI/MCP 双出口；本 spec 只交付 MCP 服务器本体，**双 transport**（stdio 本地 + Streamable-HTTP 为部署预留）。

**范围外（后续独立 spec）**：HF Spaces 部署与静态 Web 前端、CI 重建管线、上游 mooncakes.io 贡献（S5）、按需重扫（需原生引擎）。

## 2. 架构

```
LLM agent ──stdio(JSON-RPC)──┐
                             ├── indexer/mcp_server.py (FastMCP)
LLM agent ──Streamable-HTTP──┘        ├── search_modules → indexer/search.search()   (需 GLM key)
                                      └── get_module     → indexer/detail.build_module_detail()  (纯本地)
detail.py 四源装配：
  index/chunks.db             → api_surface (各包 mbti 的 pub 声明行), version
  index/packages.jsonl        → readme_summary (首 1500 字)
  results/results.jsonl       → verdict, risk, findings[{rule, severity, detail}]
  state/registry_index.json   → description, keywords, repository（结构化字段唯一来源）
```

新文件（`indexer/` 内）：

```
indexer/
├── detail.py       # build_module_detail(name) -> dict；三源装配
├── mcp_server.py   # FastMCP 实例 + 两工具注册 + 双 transport 入口
├── test_detail.py
└── test_mcp_server.py
```

## 3. 工具契约

### search_modules

```
参数: query: str, n: int = 10, verdict: str | None = None
返回: JSON 字符串: [{"module","version","score","verdict","risk","description"}]
```

- 直通 `search.search()`（同一签名与聚合语义）
- `description` 字段改为**优先 registry description**，缺失时回退最佳命中块文本（对 LLM 是语义摘要而非原文块——CLI/Web/MCP 三处受益的顺手修正）

### get_module

```
参数: name: str（如 "bobzhang/moonjq"）
返回: JSON 字符串:
{
  "name", "version", "description", "keywords", "repository",
  "verdict", "risk",
  "findings": [{"rule","severity","detail"}...],   # 全量，不截断
  "api_surface": [{"pkg", "signatures": [...]}],   # 每 package 的 mbti 中以 "pub " 开头的声明行
  "readme_summary"                                  # 首 1500 字
}
```

- 纯本地读取，**不依赖 GLM key**、不做按需重扫
- `name` 不存在 → 结构化错误（见 §4），附相近包名 top-3 建议

## 4. 错误处理（全部结构化，LLM 可读，不抛裸异常）

| 条件 | 返回 |
|---|---|
| 索引目录缺失 / chunks.db 不存在 | `{"error":"index_not_built","hint":"run: python3 -m indexer.collect && python3 -m indexer.embed"}` |
| get_module 的 name 不存在 | `{"error":"module_not_found","suggestions":[相近名 top-3]}`（difflib 近邻） |
| search 时 GLM key 缺失 | `{"error":"missing_api_key","hint":"set ZHIPUAI_API_KEY or API_KEY"}` |
| GLM 网络/限流（重试耗尽） | `{"error":"embedder_unavailable","detail":<异常摘要>}` |
| 空查询 / 超长查询 / n<1 | `{"error":"invalid_argument","detail":<ValueError 信息>}` |

- `results.jsonl` 缺失：get_module 的 verdict/risk/findings 为 `null`/`[]`，不报错
- README 缺失：`readme_summary` 为 `null`

## 5. Transport 与入口

- **stdio（默认）**：`python3 -m indexer.mcp_server`
- **Streamable-HTTP**：`python3 -m indexer.mcp_server --http --port 8000`（本地验证用；HF Spaces 部署在后续 spec 复用同一入口）
- 配置经环境变量：`INDEXER_INDEX_DIR`（默认 `index`）、`INDEXER_RESULTS_PATH`（默认 `results/results.jsonl`）、`INDEXER_REGISTRY_PATH`（默认 `state/registry_index.json`，get_module 与 description 修正共用）；GLM key 沿用 api.py 现有映射（`ZHIPUAI_API_KEY` 或 `API_KEY`）

## 6. 依赖

- **`mcp`（官方 SDK，FastMCP）— 仓库首个第三方 Python 依赖**（用户裁定，明确例外）
- 新增 `requirements.txt`：`mcp>=1.2,<2`（pin 主版本）
- 仓库其余部分维持 stdlib+numpy 纪律；mcp 仅被 `mcp_server.py`/测试导入

## 7. 测试（FastMCP in-memory client，零子进程零网络）

- 工具注册与参数 schema 快照
- `search_modules`：FakeEmbedder 全链路（正常 / verdict 过滤 / 索引缺失 / key 缺失 / 非法参数）
- `get_module`：三源装配（完整 / 缺 verdict / 缺 README / 模块不存在含 suggestions / 索引缺失）
- HTTP 模式：起 `127.0.0.1:0` 服务后 client list/call 一轮
- `detail.py` 单测独立于 MCP 层（纯函数装配）

## 8. 验收

1. `pytest indexer/ crawl/ -q` 全绿（含新 MCP/detail 测试）；`moon test` 90/90 不受影响
2. opencode/Claude Desktop 以 stdio 接入后：`search_modules("jmes")` 能取到 jq 族包，`get_module("bobzhang/moonjq")` 返回完整判断载荷（含 findings 与 API 面）
3. `--http` 模式 in-process 测试通过（真实 Spaces 部署在下一 spec 验收）
