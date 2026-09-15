///|
pub(all) struct LineIndex {
  starts : Array[Int]
} derive(Debug)

///|
pub fn LineIndex::build(s : String) -> LineIndex {
  let starts = [0]
  let n = s.length()
  for i = 0; i < n; i = i + 1 {
    if s[i] == 10 {
      starts.push(i + 1)
    }
  }
  { starts, }
}

///|
pub fn LineIndex::line_of(self : LineIndex, offset : Int) -> Int {
  // 二分：starts 中最后一个 <= offset 的下标 + 1
  let mut lo = 0
  let mut hi = self.starts.length() - 1
  let mut ans = 0
  for ; lo <= hi; {
    let mid = (lo + hi) / 2
    if self.starts[mid] <= offset {
      ans = mid
      lo = mid + 1
    } else {
      hi = mid - 1
    }
  }
  ans + 1
}

///|
pub fn LineIndex::snippet(self : LineIndex, s : String, line : Int) -> String {
  if line < 1 || line > self.starts.length() {
    return ""
  }
  let start = self.starts[line - 1]
  let n = s.length()
  let mut end = n
  for i = start; i < n; i = i + 1 {
    if s[i] == 10 {
      end = i
      break
    }
  }
  if end > start + 200 {
    end = start + 200
  }
  s[start:end].to_owned()
}

///|
fn is_digit_ascii(u : UInt16) -> Bool {
  u >= 48 && u <= 57
}

///|
fn is_alpha_ascii(u : UInt16) -> Bool {
  (u >= 65 && u <= 90) || (u >= 97 && u <= 122)
}

///|
pub fn is_b64(u : UInt16) -> Bool {
  is_alpha_ascii(u) || is_digit_ascii(u) || u == 43 || u == 47 || u == 61
}

///|
pub fn is_hex(u : UInt16) -> Bool {
  is_digit_ascii(u) || (u >= 97 && u <= 102) || (u >= 65 && u <= 70)
}

///|
pub fn longest_run(s : String, alphabet : (UInt16) -> Bool) -> Int {
  let mut best = 0
  let mut cur = 0
  let n = s.length()
  for i = 0; i < n; i = i + 1 {
    if alphabet(s[i]) {
      cur = cur + 1
      if cur > best {
        best = cur
      }
    } else {
      cur = 0
    }
  }
  best
}

///|
pub fn is_raw_ip_url(s : String) -> Bool {
  for scheme in ["http://", "https://"] {
    match s.find(scheme) {
      Some(start) => {
        let host_start = start + scheme.length()
        let n = s.length()
        let mut host_end = n
        for i = host_start; i < n; i = i + 1 {
          let u = s[i]
          if u == 47 || u == 58 {
            // '/' 或 ':'
            host_end = i
            break
          }
        }
        if host_end > host_start {
          let host = s[host_start:host_end].to_owned()
          let segs = host.split(".").collect()
          if segs.length() == 4 {
            let mut all_num = true
            for seg in segs {
              if seg.length() == 0 {
                all_num = false
              }
              for c in seg {
                if !(c >= '0' && c <= '9') {
                  all_num = false
                }
              }
            }
            if all_num {
              return true
            }
          }
        }
      }
      None => ()
    }
  }
  false
}

///|
pub fn damerau_levenshtein(a : String, b : String) -> Int {
  let la = a.length()
  let lb = b.length()
  let ca = a.to_array()
  let cb = b.to_array()
  // d[i][j]，含 OSA 转置
  let d : Array[Array[Int]] = []
  for i = 0; i <= la; i = i + 1 {
    let row : Array[Int] = []
    for j = 0; j <= lb; j = j + 1 {
      if j == 0 {
        row.push(i)
      } else if i == 0 {
        row.push(j)
      } else {
        row.push(0)
      }
    }
    d.push(row)
  }
  for i = 1; i <= la; i = i + 1 {
    for j = 1; j <= lb; j = j + 1 {
      let cost = if ca[i - 1] == cb[j - 1] { 0 } else { 1 }
      let del = d[i - 1][j] + 1
      let ins = d[i][j - 1] + 1
      let sub = d[i - 1][j - 1] + cost
      let mut v = if del < ins { del } else { ins }
      if sub < v {
        v = sub
      }
      if i > 1 && j > 1 && ca[i - 1] == cb[j - 2] && ca[i - 2] == cb[j - 1] {
        let tr = d[i - 2][j - 2] + 1
        if tr < v {
          v = tr
        }
      }
      d[i][j] = v
    }
  }
  d[la][lb]
}
