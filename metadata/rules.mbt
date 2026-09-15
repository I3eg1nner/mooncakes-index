///|
let prebuild_danger : Array[String] = [
  "curl", "wget", "http", "sh", "python", "rm -rf",
]

///|
/// S06：pre-build 钩子存在 → High；命令含危险词（下载/解释器/删除）→ Critical
pub fn s06(pkg : PkgInfo, pkgfile : String) -> Array[@engine.Finding] {
  let fs : Array[@engine.Finding] = []
  for cmd in pkg.pre_build {
    let danger = prebuild_danger.iter().any(p => cmd.contains(p))
    let sev : @engine.Severity = if danger {
      @engine.Critical
    } else {
      @engine.High
    }
    let rd : @engine.RuleDef = {
      id: "S06",
      severity: sev,
      category: @engine.Source,
      description: "pre-build hook",
    }
    fs.push(
      rd.finding(file=pkgfile, line=1, snippet=cmd, message="pre-build command"),
    )
  }
  fs
}
