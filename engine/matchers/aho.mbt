///|
pub(all) struct Hit {
  pattern : Int
  offset : Int
  length : Int
} derive(Debug, Eq)

///|
struct Automaton {
  next : Array[Map[Int, Int]]
  fail : Array[Int]
  out : Array[Array[Int]]
  pats : Array[Int]
} derive(Debug)

///|
pub fn Automaton::new(patterns : Array[String]) -> Automaton {
  let next : Array[Map[Int, Int]] = [Map([])]
  let fail : Array[Int] = [0]
  let out : Array[Array[Int]] = [[]]
  let pats : Array[Int] = []
  for pidx, p in patterns {
    pats.push(p.length())
    if p.length() == 0 {
      continue
    }
    let mut state = 0
    for j = 0; j < p.length(); j = j + 1 {
      let u = p[j].to_int()
      match next[state].get(u) {
        Some(ns) => state = ns
        None => {
          next.push(Map([]))
          fail.push(0)
          out.push([])
          let ns = next.length() - 1
          next[state][u] = ns
          state = ns
        }
      }
    }
    out[state].push(pidx)
  }
  // BFS 建失配链
  let queue : Array[Int] = []
  for _, child in next[0] {
    queue.push(child)
  }
  for qi = 0; qi < queue.length(); qi = qi + 1 {
    let s = queue[qi]
    for u, child in next[s] {
      queue.push(child)
      let mut f = fail[s]
      for ;; {
        if f == 0 {
          fail[child] = next[0].get(u).unwrap_or(0)
          break
        }
        match next[f].get(u) {
          Some(nf) => {
            fail[child] = nf
            break
          }
          None => f = fail[f]
        }
      }
      for pidx in out[fail[child]] {
        out[child].push(pidx)
      }
    }
  }
  { next, fail, out, pats }
}

///|
fn Automaton::go(self : Automaton, state : Int, u : Int) -> Int {
  let mut s = state
  for ;; {
    match self.next[s].get(u) {
      Some(ns) => return ns
      None => if s == 0 { return 0 } else { s = self.fail[s] }
    }
  }
}

///|
pub fn Automaton::scan(self : Automaton, text : String) -> Array[Hit] {
  let hits : Array[Hit] = []
  let mut state = 0
  for i = 0; i < text.length(); i = i + 1 {
    state = self.go(state, text[i].to_int())
    for pidx in self.out[state] {
      let len = self.pats[pidx]
      hits.push({ pattern: pidx, offset: i - len + 1, length: len })
    }
  }
  hits
}
