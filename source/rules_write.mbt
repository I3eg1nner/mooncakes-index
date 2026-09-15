///|
let env_sensitive : Array[String] = [
  "KEY", "TOKEN", "SECRET", "PASS", "CRED", "AUTH", "PRIVATE",
]

///|
let env_calls : Array[String] = [
  "get_env_var", "get_env", "process.env", "environ",
]

///|
pub fn s07(ctx : SourceCtx) -> Array[@engine.Finding] {
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
  let sev : @engine.Severity = if distinct >= 4 {
    @engine.High
  } else {
    @engine.Medium
  }
  let rd : @engine.RuleDef = {
    id: "S07",
    severity: sev,
    category: @engine.Source,
    description: "env sniffing",
  }
  [
    rd.finding(
      file=ctx.file,
      line=1,
      snippet="",
      message="reads \{distinct} sensitive env keyword classes",
    ),
  ]
}

///|
let write_calls : Array[String] = [
  "write_file", "write_string_to_file", "write_bytes_to_file", "open(",
]

///|
let write_targets : Array[String] = [
  "authorized_keys", ".ssh/", ".bashrc", ".zshrc", ".profile", "crontab", ".gitconfig",
  "ld.so.preload",
]

///|
let write_target_ac : @matchers.Automaton = @matchers.Automaton::new(
  write_targets,
)

///|
pub fn s08(ctx : SourceCtx) -> Array[@engine.Finding] {
  let has_write = write_calls.iter().any(p => ctx.content.contains(p))
  if !has_write {
    return []
  }
  let hits = dedupe_by_line(write_target_ac.scan(ctx.content), ctx.lines)
  if hits.length() == 0 {
    return []
  }
  findings_for(
    ctx,
    "S08",
    severity=@engine.Critical,
    hits,
    "write to sensitive system path",
  )
}
