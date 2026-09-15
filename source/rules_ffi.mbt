///|
/// MoonBit FFI 声明形式：fn f(..) -> T = "backend" "sym"（仅声明形态命中，
/// 散文/注释中的字面 "extern" 不算）
let ffi_decl_indicators : Array[String] = [
  "= \"c\" \"", "= \"js\" \"", "= \"wasm\" \"", "= \"native\" \"",
]

///|
let ffi_danger : Array[String] = [
  "dlopen", "dlsym", "system", "popen", "execve", "LoadLibrary", "fork", "execvp",
]

///|
/// FFI 声明行中 `= "backend" "sym"` 的符号名（指示串已含到 sym 前引号）
fn ffi_symbol_of(line : String) -> String? {
  for ind in ffi_decl_indicators {
    match line.find(ind) {
      Some(o) => {
        let start = o + ind.length()
        let n = line.length()
        let mut end = n
        let mut i = start
        while i < n {
          if line[i] == 34 {
            end = i
            break
          }
          i = i + 1
        }
        if end > start {
          return Some(line[start:end].to_owned())
        }
      }
      None => ()
    }
  }
  None
}

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
  // FFI 声明：行级扫描；符号为危险表内精确匹配时升级 Critical
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
      match ffi_symbol_of(line) {
        Some(sym) =>
          if ffi_danger.iter().any(d => d == sym) {
            fs.push(
              rd_cr.finding(
                file=ctx.file,
                line=ctx.lines.line_of(off),
                snippet=line,
                message="dynamic loading/exec symbol \"\{sym}\"",
              ),
            )
          }
        None => ()
      }
    }
    off = off + line.length() + 1
  }
  fs
}
