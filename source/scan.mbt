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
/// 组合升级：同文件 S01（网络）与 S02/S04（凭据/混淆）同现 → 追加一条 S99 Critical
pub fn combine_rules(fs : Array[@engine.Finding]) -> Array[@engine.Finding] {
  let out = fs.copy()
  let has = (rule : String, file : String) => {
    fs.iter().any(f => f.rule == rule && f.file == file)
  }
  let files : Array[String] = []
  for f in fs {
    if !files.iter().any(x => x == f.file) {
      files.push(f.file)
    }
  }
  for file in files {
    if has("S01", file) && (has("S02", file) || has("S04", file)) {
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
