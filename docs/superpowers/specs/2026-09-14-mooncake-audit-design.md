# mooncake-audit 设计文档

日期：2026-09-14
状态：已获用户批准

## 1. 目标与范围

为 mooncakes.io（MoonBit 社区包仓库，~2469 模块 / 22646 包）构建供应链安全审计工具，目标是发现恶意投毒包。

- **运行形态**：CLI 静态扫描器（MoonBit 编写）+ Python 批量爬取编排层。两者分离：Python 负责 registry 交互、下载、并发调度；MoonBit 引擎负责全部分析逻辑（元数据启发式 + 源码模式规则 + 评分 + 报告）。
- **检测信号**（用户选定）：① 元数据/仿冒启发式；② 源码静态分析。构建与质量信号、版本历史分析不在 v1 范围。
- **输出**：风险评分 + JSON 机器可读报告 + 终端人读摘要。
- **爬取范围**：全量（~2469 模块最新版本），支持断点续爬、限流、失败重试。
- **借鉴来源**：PyPI 侧 guarddog（Datadog）、Maloss（ICSE'20）、pip-audit；npm 侧 socket.dev 启发式、npq；学术工具 Maloss / OSSGadget；OSSF Package Analysis。

## 2. 安全边界（硬性约束）

1. 分析器对被扫包**只读不执行**：不运行 `moon check/build/run/test`，不执行 moon.pkg 的 pre-build 命令（该机制是类 npm postinstall 的攻击面，本身是重点检测对象）。
2. Python 解压源码 tarball 时做 zip-slip 防护（拒绝 `..` 路径与绝对路径条目）与单包大小上限。
3. MoonBit 引擎内不执行任何动态代码；所有 matcher 为静态字符串/结构匹配。
4. 爬虫限流（默认 ~2 req/s）、礼貌 UA、失败不中断全量任务。

## 3. 总体架构与数据流

```
┌─────────────── Python 编排层 (crawl/) ───────────────┐
│  registry_client: 索引/统计 API → 模块清单+下载计数     │
│  downloader: 按 module@version 拉源码 tarball → 解压    │
│  runner: 逐包调 moonbit 分析引擎 CLI (子进程, 超时60s)  │
│  aggregator: 合并 JSONL → 汇总报告, 断点续爬状态        │
└──────────────────────┬───────────────────────────────┘
                       │ 每包调用 (路径参数)
┌──────────────────────▼───────────────────────────────┐
│           mooncake-audit (MoonBit 分析引擎)            │
│  metadata: moon.mod/moon.pkg/readme/文件结构 启发式     │
│  source:   .mbt/.mbtx/.mbt.md 危险模式规则引擎          │
│  score:    规则加权 → risk score + verdict             │
│  report:   JSON 输出 (机器可读) + 终端彩色摘要          │
└──────────────────────────────────────────────────────┘
```

数据流：Python 爬取器从 mooncakes.io API 拉全量模块索引；`/api-new/v0/modules/statistics?raw=true` 返回 zip 内含 CSV（下载计数），该 CSV 同时作为 typosquatting 检测的"热门包名"数据源。逐包下载源码到 `corpus/<author>/<module>/<version>/`，对每包调用 MoonBit 引擎得到单包 JSON 报告，聚合产出 `results/results.jsonl` + `summary.md`。爬取状态存 `state/crawl_state.json`。

## 4. 仓库布局

```
mooncacke/
├── moon.mod              # MoonBit 模块: <author>/mooncake-audit
├── engine/               # 规则引擎核心
│   └── matchers/         # 匹配原语
├── metadata/             # moon.mod/moon.pkg 解析 + 启发式规则
├── source/               # 源码规则（.mbt/.mbtx/.mbt.md 扫描）
├── score/                # 评分
├── report/               # JSON + 终端输出
├── cmd/main/             # MoonBit CLI 入口
├── canaries/             # 恶意样本测试集（合成投毒包 fixture）
├── crawl/                # Python 编排层
├── .opencode/skills/moonbit-agent-guide/   # 项目级 skill
├── docs/superpowers/specs/
└── results/ state/ corpus/               # 运行产物（gitignore）
```

## 5. MoonBit 分析引擎

### 5.1 包划分

| 包 | 职责 | 关键类型 |
|---|---|---|
| `engine/` | 规则接口、结果收集、按文件类型分派 | `Rule`（id/severity/category/description/matcher_fn）、`Finding`（rule_id, file, line, snippet, message） |
| `engine/matchers/` | 匹配原语：字面子串、多模式 Aho-Corasick（自实现）、行扫描、hex/base64 长度与字符集检测 | `Matcher::find(text) -> Array[Span]` |
| `metadata/` | 解析 `moon.mod`/`moon.pkg`（v1 手写极简解析器，不引入第三方 toml 依赖——安全工具自身避免供应链面）+ M 系列规则 | `ModuleInfo`, `PkgInfo` |
| `source/` | S 系列源码规则，逐文件扫描 | 规则目录（见 §6） |
| `score/` | `risk = Σ weight(severity)`，映射 verdict | `Verdict { Clean, Suspicious, Malicious }` |
| `report/` | JSON 序列化（derive ToJson）+ 终端彩色摘要 | `Report { module, version, findings, risk, verdict }` |
| `cmd/main/` | CLI：`mooncake-audit scan <dir> [--json] [--min-severity s]` | async main |

### 5.2 规则引擎设计

每条规则 = `(id, severity, category, description, matcher_fn)`。引擎按文件类型分派规则集（`.mbt/.mbtx/.mbt.md` → S 规则；`moon.mod/moon.pkg/README` → M 规则），收集 `Finding`。新增规则 = 新增文件 + 注册 + 快照测试。单文件扫描失败降级为 warning finding，不 panic（`catch` 包裹）。

### 5.3 评分模型

- severity 权重：Critical=25, High=10, Medium=5, Low=1
- 同一规则多文件命中取最大一次计分；不同规则累加；封顶 100
- verdict：`risk ≥ 50 → Malicious`，`≥ 15 → Suspicious`，否则 `Clean`

## 6. 规则清单（核心资产）

### 6.1 元数据/仿冒启发式（M 系列）

| ID | 规则 | severity | 来源 |
|---|---|---|---|
| M01 | typosquatting：包名对热门包名表（statistics CSV 生成）Damerau-Levenshtein ≤2 且非同一作者 | High | guarddog/PyPI |
| M02 | 官方仿冒：名字含 `moonbitlang/` 前缀但作者 ≠ moonbitlang；仿 `core/async/x` 官方包名 | Critical | npm typo 规则 |
| M03 | 空壳包：无 README 或 README < 200 字符，且无任何测试文件，且 README 声称提供库功能 | Medium | Maloss |
| M04 | 元数据不一致：repository 指向不存在/不相关仓库 | Medium | OSSGadget |
| M05 | 依赖混淆：依赖名与官方模块高度相似 | High | socket.dev |

### 6.2 源码静态分析（S 系列，扫描 `.mbt/.mbtx/.mbt.md`）

| ID | 规则 | 默认 severity |
|---|---|---|
| S01 | 网络外传：`@http`/async http 客户端 POST 到硬编码 IP/非常见域名、raw IP URL | High（组合升级 Critical） |
| S02 | 凭据访问：字符串模式 `.ssh`、`.aws/credentials`、`.npmrc`、`id_rsa`、`credential`、`token`、`api_key` 与文件读组合 | High |
| S03 | 进程执行：`@shell.Cmd`/`spawn` 出现即 Medium；叠加危险参数（`curl`、`wget`、`bash`）升级 Critical | Medium/Critical |
| S04 | 混淆：长 base64/hex 字符串（>80 字符）、字符数组拼接解密、异或循环 | High |
| S05 | 动态执行/FFI：`extern "C"` 声明 + dlopen/system 类符号 | Critical |
| S06 | pre-build 命令：moon.pkg 中出现 `pre-build`/构建钩子且涉及网络或进程 | Critical |
| S07 | 环境变量嗅探：批量 `@env` 读取敏感键（KEY/TOKEN/SECRET/PASS） | Medium |
| S08 | 可疑写入：向 `~/.ssh/authorized_keys`、crontab、shell rc 文件写内容 | Critical |

具体模式串与升级/降级条件在实现计划中逐条定义并以 canary 用例锁定。

## 7. Python 编排层（crawl/）

模块：`registry.py`（API 客户端：模块索引、statistics CSV 解析、版本列表）、`download.py`（tarball 下载 + 安全解压）、`runner.py`（并发调 MoonBit 引擎，进程池 `--workers N` 默认 4）、`state.py`（断点续爬）、`crawl.py`（CLI：`--modules all|file:|sample:N`、`--rate-limit`、重试 3 次指数退避）、`report.py`（生成 `summary.md`，按 risk 降序、Malicious/Suspicious 分组）。

全量流程：`python3 -m crawl.crawl --modules all` → 拉索引 → 逐模块下载最新版本（`--all-versions` 可选）→ 逐包调 `mooncake-audit scan <dir> --json` → 追加 `results/results.jsonl` → `summary.md`。限流默认 ~2 req/s，UA 标识审计工具。容错：下载失败/引擎崩溃/单包超时（引擎进程 60s）记入 state failures，供重跑。

## 8. 测试与验证策略

MoonBit 侧（moon test 快照测试）：
- 每条规则一个 canary 用例：`canaries/` 合成恶意样本片段作 fixture，断言命中规则 ID 与行号
- 良性样本：从官方 moonbitlang/core 取典型代码，断言零误报
- 匹配器单测（Damerau-Levenshtein、Aho-Corasick、行扫描）
- 评分边界测试（50/15 阈值）

端到端：
- `canaries/` 完整合成投毒包（恶意 moon.mod + 源码）必须 verdict=Malicious
- 对官方包试跑（core/async/x）必须全 Clean
- 全量爬取前先 `--sample:50` 试运行验证管道，再放全量

## 9. 实战验证阶段（开发完成后）

1. `--sample:50` 试运行 → 检查误报率与管道稳定性
2. 全量爬取 ~2469 模块 → `results.jsonl` + `summary.md`
3. 对 Malicious/Suspicious 命中逐条人工复核（读源码确认），产出真实投毒包发现报告（如有）
