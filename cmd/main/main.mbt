///|
pub(all) enum Cmd {
  Scan(
    dir~ : String,
    module~ : String,
    version~ : String,
    hotlist~ : String,
    json~ : Bool,
    min_sev~ : Int
  )
  Help
} derive(Debug)

///|
pub fn parse_args(args : Array[String]) -> Cmd {
  if args.length() == 0 || args[0] != "scan" {
    return Help
  }
  let mut dir = ""
  let mut module = ""
  let mut version = ""
  let mut hotlist = ""
  let mut json = false
  let mut min_sev = 0
  let n = args.length()
  let mut i = 1
  while i < n {
    let a = args[i]
    if a == "--json" {
      json = true
    } else if a is ("--module" | "--version" | "--hotlist" | "--min-severity") {
      if i + 1 < n {
        i += 1
        match a {
          "--module" => module = args[i]
          "--version" => version = args[i]
          "--hotlist" => hotlist = args[i]
          _ =>
            min_sev = match @engine.parse_severity(args[i]) {
              Some(s) => s.rank()
              None => 0
            }
        }
      }
      // flag missing its value at the end: ignore the flag
    } else if a.has_prefix("--") {
      () // unknown flag: ignore
    } else if dir is "" {
      dir = a
    }
    i += 1
  }
  Scan(dir~, module~, version~, hotlist~, json~, min_sev~)
}

///|
pub async fn load_hotlist(path : String) -> Array[String] {
  if path is "" {
    return []
  }
  try {
    let text = @fs.read_file(path).text()
    text
    .split("\n")
    .map(l => l.trim(chars=" \t\r").to_owned())
    .filter(l => l.length() > 0)
    .collect()
  } catch {
    _ => []
  }
}

///|
pub fn filter_min(r : @report.Report, min_rank : Int) -> @report.Report {
  if min_rank <= 0 {
    return r
  }
  let kept = r.findings.filter(f => f.severity.rank() >= min_rank)
  let risk = @score.risk_of(kept)
  { ..r, findings: kept, risk, verdict: @score.verdict_of(risk).to_string() }
}

///|
fn usage() -> String {
  "usage: mooncake-audit scan <dir> [--module m] [--version v] [--hotlist file] [--json] [--min-severity low|medium|high|critical]"
}

///|
async fn main {
  let args = @env.args()
  let user_args : Array[String] = if args.length() > 1 {
    args[1:].to_owned()
  } else {
    []
  }
  match parse_args(user_args) {
    Help => println(usage())
    Scan(..) as c => {
      let r = try {
        let opts : @scan.ScanOptions = {
          hotlist: load_hotlist(c.hotlist),
          authoritative_name: c.module,
        }
        @scan.run_scan(c.dir, opts)
      } catch {
        e => {
          let err : Json = { "module": c.dir, "error": "\{e}" }
          println(err.stringify())
          return
        }
      }
      let r = if !(c.module is "") { { ..r, module: c.module } } else { r }
      let r = if !(c.version is "") { { ..r, version: c.version } } else { r }
      let r = filter_min(r, c.min_sev)
      if c.json {
        println(r.to_json_string())
      } else {
        println(@report.human_summary(r))
      }
    }
  }
}
