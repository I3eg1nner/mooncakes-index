///|
let http_client_indicators : Array[String] = [
  "@http.", "HttpClient", "http.get", "http.post", "request(",
]

///|
fn find_from(s : String, pat : String, from : Int) -> Int? {
  let n = s.length()
  let m = pat.length()
  if m == 0 || n < m {
    return None
  }
  let limit = n - m
  let mut i = from
  while i <= limit {
    let mut ok = true
    for j = 0; j < m; j = j + 1 {
      if s[i + j] != pat[j] {
        ok = false
        break
      }
    }
    if ok {
      return Some(i)
    }
    i = i + 1
  }
  None
}

///|
fn is_raw_ip_host(host : String) -> Bool {
  let segs = host.split(".").collect()
  if segs.length() != 4 {
    return false
  }
  for seg in segs {
    if seg.length() == 0 {
      return false
    }
    for c in seg {
      if !(c >= '0' && c <= '9') {
        return false
      }
    }
  }
  true
}

///|
pub fn s01(ctx : SourceCtx) -> Array[@engine.Finding] {
  let fs : Array[@engine.Finding] = []
  let rd_hi : @engine.RuleDef = {
    id: "S01",
    severity: @engine.High,
    category: @engine.Source,
    description: "network exfiltration",
  }
  // 扫描所有 scheme 出现位置，host 为点分数字（raw IP）→ High
  let n = ctx.content.length()
  for scheme in ["http://", "https://"] {
    let mut from = 0
    for ;; {
      match find_from(ctx.content, scheme, from) {
        None => break
        Some(start) => {
          let host_start = start + scheme.length()
          let mut host_end = n
          for i = host_start; i < n; i = i + 1 {
            let u = ctx.content[i]
            let digit = u >= 48 && u <= 57
            if !(digit || u == 46) {
              // 非数字/非点号即 host 结束（覆盖 '/'、':'、引号等）
              host_end = i
              break
            }
          }
          if host_end > host_start {
            let host = ctx.content[host_start:host_end].to_owned()
            if is_raw_ip_host(host) {
              let line = ctx.lines.line_of(start)
              fs.push(
                rd_hi.finding(
                  file=ctx.file,
                  line~,
                  snippet=ctx.lines.snippet(ctx.content, line),
                  message="URL with raw IP address",
                ),
              )
            }
          }
          from = start + scheme.length()
          if from >= n {
            break
          }
        }
      }
    }
  }
  // http 客户端调用指示：无 raw IP 命中时记 Low（供 S99 组合规则消费）
  if fs.length() == 0 {
    let ac = @matchers.Automaton::new(http_client_indicators)
    let hits = dedupe_by_line(ac.scan(ctx.content), ctx.lines)
    if hits.length() > 0 {
      let rd_low : @engine.RuleDef = {
        id: "S01",
        severity: @engine.Low,
        category: @engine.Source,
        description: "http client usage",
      }
      for h in hits {
        let line = ctx.lines.line_of(h.offset)
        fs.push(
          rd_low.finding(
            file=ctx.file,
            line~,
            snippet=ctx.lines.snippet(ctx.content, line),
            message="http client usage",
          ),
        )
      }
    }
  }
  fs
}
