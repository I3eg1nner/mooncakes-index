///|
pub(all) struct SourceCtx {
  file : String
  content : String
  lines : @matchers.LineIndex
} derive(Debug)

///|
/// 同一命中行去重：一行内多个关键词只产出一条 finding
fn dedupe_by_line(
  hits : Array[@matchers.Hit],
  lines : @matchers.LineIndex,
) -> Array[@matchers.Hit] {
  let out : Array[@matchers.Hit] = []
  let mut last = 0
  for h in hits {
    let line = lines.line_of(h.offset)
    if out.length() == 0 || line != last {
      out.push(h)
      last = line
    }
  }
  out
}

///|
fn findings_for(
  ctx : SourceCtx,
  rule : String,
  severity~ : @engine.Severity,
  hits : Array[@matchers.Hit],
  message : String,
) -> Array[@engine.Finding] {
  let rd : @engine.RuleDef = {
    id: rule,
    severity,
    category: @engine.Source,
    description: message,
  }
  let fs : Array[@engine.Finding] = []
  for h in hits {
    let line = ctx.lines.line_of(h.offset)
    let snippet = ctx.lines.snippet(ctx.content, line)
    fs.push(rd.finding(file=ctx.file, line~, snippet~, message~))
  }
  fs
}

///|
fn contains_any(s : String, pats : Array[String]) -> Bool {
  for p in pats {
    match s.find(p) {
      Some(_) => return true
      None => ()
    }
  }
  false
}

///|
/// 最长字符集连续段及其起始偏移（UTF-16 code unit），供 S04 定位行号
fn longest_run_at(s : String, alphabet : (UInt16) -> Bool) -> (Int, Int) {
  let n = s.length()
  let mut best = 0
  let mut best_at = 0
  let mut cur = 0
  let mut cur_at = 0
  for i = 0; i < n; i = i + 1 {
    if alphabet(s[i]) {
      if cur == 0 {
        cur_at = i
      }
      cur = cur + 1
      if cur > best {
        best = cur
        best_at = cur_at
      }
    } else {
      cur = 0
    }
  }
  (best, best_at)
}
