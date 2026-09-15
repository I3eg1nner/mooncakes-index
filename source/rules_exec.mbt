///|
/// OS 进程执行指示：MoonBit 中进程执行仅经 @shell 包（async shell）；
/// `spawn(` 不在此列（MoonBit 任务/协程 spawn 并非进程执行）；
/// libc system/popen 等需 FFI 声明，归 S05 管。
let exec_indicators : Array[String] = ["@shell.Cmd", "@shell.Pipeline"]

///|
let dangerous_args : Array[String] = [
  "curl", "wget", "bash", "sh -c", "python", "nc ", "eval",
]

///|
let exec_ac : @matchers.Automaton = @matchers.Automaton::new(exec_indicators)

///|
pub fn s03(ctx : SourceCtx) -> Array[@engine.Finding] {
  let hits = dedupe_by_line(exec_ac.scan(ctx.content), ctx.lines)
  if hits.length() == 0 {
    return []
  }
  let danger = contains_any(ctx.content, dangerous_args)
  let sev = if danger { @engine.Critical } else { @engine.Medium }
  findings_for(
    ctx,
    "S03",
    severity=sev,
    hits,
    if danger {
      "process execution with dangerous argument"
    } else {
      "process execution"
    },
  )
}
