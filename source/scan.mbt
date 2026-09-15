///|
/// 测试辅助：以默认文件名构造 SourceCtx
pub fn mkctx_for_test(content : String) -> SourceCtx {
  { file: "src/x.mbt", content, lines: @matchers.LineIndex::build(content) }
}

///|
/// 待审计源码文件分类：.mbt / .mbtx / .mbt.md（排除 moon.pkg、moon.mod 等）
pub fn is_source_file(name : String) -> Bool {
  name.has_suffix(".mbt") ||
  name.has_suffix(".mbtx") ||
  name.has_suffix(".mbt.md")
}

///|
/// `.mbt.md` 文档：围栏代码块（``` 起止）之外的行替换为空行，行数不变以
/// 保持 LineIndex 行号与原文一致；S 规则只扫描过滤后的围栏内容。
pub fn extract_fenced_code(content : String) -> String {
  let lines : Array[String] = []
  let mut in_fence = false
  for line in content.split("\n") {
    if line.trim(chars=" \t").has_prefix("```") {
      in_fence = !in_fence
      lines.push("")
    } else if in_fence {
      lines.push(line.to_owned())
    } else {
      lines.push("")
    }
  }
  lines.join("\n")
}

///|
/// 组合升级：同文件 S01（网络）与 S02/S04（凭据/混淆）同现 → 追加一条 S99 Critical。
/// 双方 feeder 均需 High 及以上（S01 raw-IP、S02 凭据读取、S04 混淆），
/// Low+Low（http client 用法 + 注释中的凭据词）组合不足以升级。
pub fn combine_rules(fs : Array[@engine.Finding]) -> Array[@engine.Finding] {
  let out = fs.copy()
  let has_high = (rule : String, file : String) => {
    fs
    .iter()
    .any(f => {
      f.rule == rule &&
      f.file == file &&
      f.severity.rank() >= @engine.High.rank()
    })
  }
  let files : Array[String] = []
  for f in fs {
    if !files.iter().any(x => x == f.file) {
      files.push(f.file)
    }
  }
  for file in files {
    if has_high("S01", file) && (has_high("S02", file) || has_high("S04", file)) {
      let rd : @engine.RuleDef = {
        id: "S99",
        severity: @engine.Critical,
        category: @engine.Source,
        description: "exfil combo",
      }
      out.push(
        rd.finding(
          file~,
          line=1,
          snippet="",
          message="S01 network + credential/obfuscation in same file",
        ),
      )
    }
  }
  out
}
