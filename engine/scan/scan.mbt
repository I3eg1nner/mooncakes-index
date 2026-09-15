///|
pub(all) struct ScanOptions {
  hotlist : Array[String]
  /// 注册表权威模块名（来自 mooncakes.io 索引；直扫本地目录时为 ""）
  authoritative_name : String
} derive(Debug)

///|
fn basename(p : String) -> String {
  match p.rev_find("/") {
    Some(i) => p[i + 1:].to_owned()
    None => p
  }
}

///|
fn rel(base : String, p : String) -> String {
  if p.length() > base.length() {
    p[base.length() + 1:].to_owned()
  } else {
    p
  }
}

///|
async fn walk_files(dir : String, acc : Array[String]) -> Unit {
  for name in @fs.readdir(dir) {
    let p = dir + "/" + name
    match @fs.kind(p, follow_symlink=false) {
      SymLink => ()
      Directory => walk_files(p, acc)
      _ => acc.push(p)
    }
  }
}

///|
async fn read_opt(path : String) -> String? {
  Some(@fs.read_file(path).text()) catch {
    _ => None
  }
}

///|
pub async fn run_scan(root : String, opts : ScanOptions) -> @report.Report {
  let errors : Array[String] = []
  let findings : Array[@engine.Finding] = []
  // manifest
  let mtext = match read_opt(root + "/moon.mod") {
    Some(t) => t
    None => ""
  }
  let manifest = match @metadata.parse_manifest(mtext) {
    Some(m) => Some(m)
    None =>
      match @metadata.parse_manifest_json(mtext) {
        Some(m) => Some(m)
        None => {
          let jtext = match read_opt(root + "/moon.mod.json") {
            Some(t) => t
            None => ""
          }
          match @metadata.parse_manifest_json(jtext) {
            Some(m) => Some(m)
            None => {
              errors.push("cannot parse moon.mod")
              None
            }
          }
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
  // walk all files under root
  let files : Array[String] = []
  walk_files(root, files)
  let mut readme_len = 0
  let mut has_tests = false
  for p in files {
    let name = basename(p)
    if name.has_prefix("README") {
      match read_opt(p) {
        Some(t) => if t.length() > readme_len { readme_len = t.length() }
        None => ()
      }
    }
    if name.has_suffix("_test.mbt") || name.has_suffix("_wbtest.mbt") {
      has_tests = true
    }
  }
  // metadata rules (findings carry file "moon.mod")
  match manifest {
    Some(m) => {
      let auth = opts.authoritative_name
      // M06：manifest 声明名与注册表权威名不一致（仿冒信号）
      if auth != "" && m.name != auth {
        let rd06 : @engine.RuleDef = {
          id: "M06",
          severity: @engine.High,
          category: @engine.Metadata,
          description: "manifest name mismatch",
        }
        findings.push(
          rd06.finding(
            file="moon.mod",
            line=1,
            snippet=m.name,
            message="manifest name \{m.name} != registry name \{auth}",
          ),
        )
      }
      for f in @metadata.m01(m, opts.hotlist, authoritative=auth) {
        findings.push({ ..f, file: "moon.mod" })
      }
      for f in @metadata.m02(m, authoritative=auth) {
        findings.push({ ..f, file: "moon.mod" })
      }
      for f in @metadata.m03(m, readme_len, has_tests) {
        findings.push({ ..f, file: "moon.mod" })
      }
      for f in @metadata.m04(m, authoritative=auth) {
        findings.push({ ..f, file: "moon.mod" })
      }
      for f in @metadata.m05(m, opts.hotlist) {
        findings.push({ ..f, file: "moon.mod" })
      }
    }
    None => ()
  }
  // pkg files → S06; source files → all source rules
  let rules = @source.all_source_rules()
  for p in files {
    let name = basename(p)
    let relp = rel(root, p)
    if name is "moon.pkg" || name is "moon.pkg.json" {
      match read_opt(p) {
        Some(t) =>
          for f in @metadata.s06(@metadata.parse_pkg(t), relp) {
            findings.push(f)
          }
        None => ()
      }
    } else if @source.is_source_file(name) {
      match read_opt(p) {
        Some(content) => {
          let scanned = if name.has_suffix(".mbt.md") {
            @source.extract_fenced_code(content)
          } else {
            content
          }
          let ctx : @source.SourceCtx = {
            file: relp,
            content: scanned,
            lines: @matchers.LineIndex::build(scanned),
          }
          for rule in rules {
            let (_, rulefn) = rule
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
