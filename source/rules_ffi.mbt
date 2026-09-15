///|
/// MoonBit FFI 声明形式：fn f(..) -> T = "backend" "sym"（仅声明形态命中，
/// 散文/注释中的字面 "extern" 不算）
let ffi_decl_indicators : Array[String] = [
  "= \"c\" \"", "= \"js\" \"", "= \"wasm\" \"", "= \"native\" \"",
]

///|
let ffi_danger : Array[String] = [
  "dlopen", "dlsym", "system(", "popen(", "execve", "LoadLibrary",
]

///|
pub fn s05(ctx : SourceCtx) -> Array[@engine.Finding] {
  let fs : Array[@engine.Finding] = []
  let rd_md : @engine.RuleDef = {
    id: "S05",
    severity: @engine.Medium,
    category: @engine.Source,
    description: "extern declaration",
  }
  let rd_cr : @engine.RuleDef = {
    id: "S05",
    severity: @engine.Critical,
    category: @engine.Source,
    description: "dynamic code loading",
  }
  // FFI 声明：行级扫描
  let mut off = 0
  for line_view in ctx.content.split("\n") {
    let line = line_view.to_owned()
    if contains_any(line, ffi_decl_indicators) {
      fs.push(
        rd_md.finding(
          file=ctx.file,
          line=ctx.lines.line_of(off),
          snippet=line,
          message="FFI extern declaration",
        ),
      )
    }
    off = off + line.length() + 1
  }
  // 动态加载/执行符号：每模式首个出现位置
  for p in ffi_danger {
    match ctx.content.find(p) {
      Some(o) => {
        let line = ctx.lines.line_of(o)
        fs.push(
          rd_cr.finding(
            file=ctx.file,
            line~,
            snippet=ctx.lines.snippet(ctx.content, line),
            message="dynamic loading/exec symbol \"\{p}\"",
          ),
        )
      }
      None => ()
    }
  }
  fs
}
