///|
test "aho corasick basic" {
  let ac = @matchers.Automaton::new(["ssh", "token", "http"])
  let hits = ac.scan("see ssh and http token")
  inspect(hits.length(), content="3")
  inspect(hits[0].pattern, content="0")
  inspect(hits[1].pattern, content="2")
  inspect(hits[2].pattern, content="1")
  inspect(hits[0].offset, content="4")
}

///|
test "aho corasick overlap and failure links" {
  let ac = @matchers.Automaton::new(["he", "she", "his", "hers"])
  let hits = ac.scan("ushers")
  // "she"@1 "he"@2 "hers"@2，按扫描顺序 pattern 为 1,0,3；排序后 [0,1,3]
  inspect(hits.length(), content="3")
  let pats = hits.map(h => h.pattern)
  pats.sort()
  debug_inspect(pats, content="[0, 1, 3]")
}

///|
test "aho corasick empty text" {
  let ac = @matchers.Automaton::new(["x"])
  inspect(ac.scan("").length(), content="0")
}

///|
test "aho corasick utf-16 code unit alignment" {
  // 🚀 为代理对（2 个 code unit）+ 空格 = 命中前 3 个 unit
  let ac = @matchers.Automaton::new(["ssh"])
  let hits = ac.scan("🚀 ssh")
  inspect(hits.length(), content="1")
  inspect(hits[0].offset, content="3")
  inspect(hits[0].length, content="3")
  // 含非 BMP 字符的 pattern 同样按 unit 插入/匹配："x🚀y" 中 🚀 起始于 unit 1，长 2
  let ac2 = @matchers.Automaton::new(["🚀"])
  let hits2 = ac2.scan("x🚀y")
  inspect(hits2.length(), content="1")
  inspect(hits2[0].offset, content="1")
  inspect(hits2[0].length, content="2")
}
