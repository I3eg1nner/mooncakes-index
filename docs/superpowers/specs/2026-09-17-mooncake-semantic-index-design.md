# mooncake-semantic-index 设计文档

日期：2026-09-17
状态：已获用户批准

## 1. 目标与范围

为 mooncakes.io 生态构建**语义级包检索工具**，让 MoonBit 开发者用自然语言/意图找到包，而不依赖关键词字面匹配。

**动机用例（实测）**：`bobzhang/moonjq` 是一个 jq 实现（即 JMESPath 同族的 JSON 查询工具），但其元数据（description "A jq implementation in MoonBit"、keywords `jq/json/query`）与 README 中均不含 "jmes" 一词。官方搜索（Meilisearch 词法匹配）查 `jmes` 返回 **0 结果**，开发者会误以为该工具不存在。语义检索要求：`query("jmes")` 命中 `moonjq`（embedding 空间中 jq ≈ JMESPath）。

- **服务对象**：MoonBit 开发者（找包），不是安全研究人员。审计 verdict 仅作为附加元数据随结果返回。
- **索引内容**（用户选定）：元数据（name/version/description/keywords）+ README + API 签名（`pkg.generated.mbti`）。
- **embedding**（用户选定）：云端 API，GLM（智谱）embedding-3。
- **查询入口**（用户选定）：CLI + 本地 Web 单页。
- **数据基础**：复用本仓库已完成的爬取产物（`corpus/` 全量解包源码、`state/registry_index.json` 元数据缓存、`results/results.jsonl` 审计结果），**不做任何新的 registry 抓取**。

## 2. 非目标（YAGNI）

- 不引入向量数据库/FAISS/Qdrant——~2500 模块 × 若干块 ≈ 几万向量，numpy 暴力余弦足够（亚毫秒级）。
- 不运行 `moon info` 为缺 mbti 的包生成签名——v1 只索引已存在的 `pkg.generated.mbti`，collect 汇总覆盖率供后续决策。
- 不做新版本增量抓取——语料刷新仍走现有 crawl 流程；刷新后重跑 collect 即可，embed 有断点续跑。
- 不发布为 mooncakes 模块/独立仓库——留在本仓库 `indexer/` 目录。
- 不改 crawl/ 任何现有代码。

## 3. 总体架构与数据流

```
                      ┌─> index/packages.jsonl（收集产物，可复查）
corpus/（已有）──collect┤
state/registry_index.json ──┘└─> index/chunks.db（切块，collect 预填）
                                     │
                                     embed（填向量）──> index/vectors.npy (float32 [N,1024])
results/results.jsonl ────────────────(查询时 join verdict)────────┐
                                                                  │
                            indexer.search（CLI） ◄───────────────┤
                            indexer.serve（本地 Web）◄────────────┘
```

`indexer/` 为与 `crawl/` 平级的 Python 包，四个模块：

```
indexer/
├── collect.py   # 语料收集 + 切块素材
├── embed.py     # 切块 + GLM embedding + 断点
├── search.py    # CLI 检索
└── serve.py     # stdlib Web 服务
```

## 4. 数据模型

### `index/packages.jsonl`（collect 产物，一模块一行）

```json
{"name":"bobzhang/moonjq","version":"0.1.2",
 "description":"A jq implementation in MoonBit","keywords":["jq","json","query"],
 "readme":"<README 全文，截断 8KB>",
 "mbti":[{"pkg":"cmd/cat","text":"<pkg.generated.mbti 全文>"}]}
```

### `index/chunks.db`（SQLite）

```sql
CREATE TABLE chunks(
  id INTEGER PRIMARY KEY,     -- 与 vectors.npy 行号对齐
  module TEXT NOT NULL,       -- "bobzhang/moonjq"
  version TEXT NOT NULL,
  chunk_type TEXT NOT NULL,   -- 'meta' | 'readme' | 'mbti'
  label TEXT,                 -- mbti 块为包相对路径；readme 块为小节标题
  text TEXT NOT NULL
);
```

### `index/vectors.npy`

float32 `[N, 1024]`，行 i 对应 `chunks.id = i`，写入前 L2 归一化。

### `state/index_state.json`（embed 断点）

```json
{"bobzhang/moonjq": {"version":"0.1.2","chunks":7,"embedded_at":"..."}}
```

## 5. 组件设计

### collect.py

遍历 `corpus/<author>/<module>/`：

- **元数据**：从 registry index 取（复用 `crawl/registry.fetch_module_index()`，结果缓存到 `state/registry_index.json`；缓存缺失时联网拉取一次）。
- **README**：模块根目录按 `README.md > README.mbt.md > README*.md 变体` 优先级取一个；截断 8KB。
- **API 签名**：递归收集 `**/pkg.generated.mbti`，记录包相对路径；无则跳过并计入覆盖率统计。
- **切块**（collect 内完成，一并写入 packages.jsonl 前先切块入 SQLite）：
  - `meta` 块 ×1：name + version + description + keywords 拼接
  - `readme` 块：按 markdown 标题分节，超长节再按 ~500 token 切
  - `mbti` 块：每个 package 一块（含包路径前缀行）
- 产出 `index/packages.jsonl` + 预填充的 `index/chunks.db`。

### embed.py

读取 chunks 表中未向量化部分，批量调 GLM embedding-3，写 `index/vectors.npy`，逐模块更新 `state/index_state.json`。module@version 已 checkpoint 且 chunk 数一致 → 跳过。

### search.py（CLI）

加载 npy + chunks.db → query 文本调 embedding → 归一化后 `V @ q` → top-N → 按 module 名 join `results/results.jsonl` 的 verdict/risk → 输出。

### serve.py（Web）

stdlib `http.server.ThreadingHTTPServer`：

- `GET /` → 内嵌单页 HTML（搜索框、结果卡片：包名 / 分数 / verdict 徽章 / description 摘要；前端 fetch `/api/search`）
- `GET /api/search?q=&n=&verdict=` → JSON，结构与 CLI `--json` 完全一致

## 6. 外部依赖与配置

| 项 | 值 |
|---|---|
| API | `POST https://open.bigmodel.cn/api/paas/v4/embeddings` |
| 模型 | `embedding-3`，`dimensions=1024`（API 支持 256/512/1024/2048） |
| 鉴权 | 环境变量 `ZHIPUAI_API_KEY`，Bearer 头 |
| 批量/限流 | 批量大小与速率上限实现期实测确定，默认保守（~2 req/s），失败指数退避重试 |
| Python 依赖 | 仅标准库（urllib/json/sqlite3/http.server/numpy 之外不新增三方依赖；numpy 已在环境） |

## 7. 错误处理

- 无 `ZHIPUAI_API_KEY` → embed/search/serve 启动即报错，提示设置方法，exit code 非 0。
- API 429/网络错误 → 指数退避重试（上限若干次），重试耗尽则报错；已完成的向量不丢（checkpoint）。
- 无 README / 无 mbti 的包 → 仅 meta 块索引，collect 结束打印覆盖率（`readme: 2310/2499, mbti: 1120/2499` 风格）。
- `results.jsonl` 缺某模块 → verdict/risk 为 `null`，不失败。
- 非 UTF-8 / 异常文件 → `errors="replace"` 读取。
- 空 query / 超长 query → CLI 参数校验报错。

## 8. 测试策略（pytest，风格随 crawl/）

- **单测（无网络）**：README 优先级选择；切块边界（标题切分、超长切分）；verdict join（含缺失）；checkpoint 跳过与续跑；覆盖统计。
- **fake embedder**：定义 `embed(texts: list[str]) -> np.ndarray` 协议，测试注入确定性 fake（如词哈希向量），全链路不联网。
- **黄金用例（集成，需 API key，缺 key 自动 skip）**：对真实语料建索引后 `query("jmes")` → `bobzhang/moonjq` 出现在 top-5。此用例同时是验收标准与回归测试。
- **Web**：`serve` 的 `/api/search` 与 CLI `--json` 输出同构性测试。

## 9. 里程碑与验收

1. collect（含切块、覆盖率统计）+ 单测 —— 无网络即可完成
2. embed（GLM 批量、限流、断点）+ fake 单测
3. search CLI（verdict join、表格/JSON 输出）+ 单测
4. serve（单页 + /api/search）+ 同构测试
5. 真实全量语料构建 + 黄金用例通过

**验收标准**：`query("jmes")` → `bobzhang/moonjq` @ top-5；`moon test` 全绿 + `pytest` 全绿；全量 ~2500 模块索引构建可中断续跑。
