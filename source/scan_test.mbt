///|
test "combine escalates exfil combo" {
  let f1 : @engine.Finding = {
    rule: "S01",
    severity: @engine.High,
    category: @engine.Source,
    file: "a.mbt",
    line: 1,
    snippet: "",
    message: "",
  }
  let f2 : @engine.Finding = { ..f1, rule: "S04" }
  let out = @source.combine_rules([f1, f2])
  inspect(out.length(), content="3")
  inspect(out[2].rule, content="S99")
  debug_inspect(out[2].severity, content="Critical")
  inspect(out[2].message.contains("S01"), content="true")
}

///|
test "combine escalation preconditions" {
  let base : @engine.Finding = {
    rule: "S02",
    severity: @engine.High,
    category: @engine.Source,
    file: "a.mbt",
    line: 1,
    snippet: "",
    message: "",
  }
  let s04 : @engine.Finding = { ..base, rule: "S04" }
  let s01 : @engine.Finding = { ..base, rule: "S01" }
  // S02+S04 同文件但缺 S01：不升级
  inspect(@source.combine_rules([base, s04]).length(), content="2")
  // S01 单独出现：不升级
  inspect(@source.combine_rules([s01]).length(), content="1")
  // S01 与 S02 分处不同文件：不跨文件组合
  let other : @engine.Finding = { ..s01, file: "b.mbt" }
  inspect(@source.combine_rules([other, base]).length(), content="2")
  // 同文件 S01+S02+S04：只追加一条 S99
  let out = @source.combine_rules([s01, base, s04])
  inspect(out.length(), content="4")
  let mut n99 = 0
  for f in out {
    if f.rule == "S99" {
      n99 = n99 + 1
    }
  }
  inspect(n99, content="1")
}

///|
test "source file classification" {
  inspect(@source.is_source_file("a.mbt"), content="true")
  inspect(@source.is_source_file("a.mbtx"), content="true")
  inspect(@source.is_source_file("a.mbt.md"), content="true")
  inspect(@source.is_source_file("a.txt"), content="false")
  inspect(@source.is_source_file("moon.pkg"), content="false")
  inspect(@source.is_source_file("moon.mod"), content="false")
}

///|
test "extract_fenced_code blanks prose keeps code and line numbers" {
  let doc = "intro prose\n```\nlet a = system(\"curl\")\n```\noutro prose"
  inspect(
    @source.extract_fenced_code(doc),
    content=(
      #|
      #|
      #|let a = system("curl")
      #|
      #|
    ),
  )
}

///|
test "s03 sees mbt.md tokens inside fences only" {
  let doc = "prose says @shell.Cmd(\"curl\") casually\n```\n@shell.Cmd(\"curl\", [\"http://x\"]) |> ignore\n```\n"
  let fs = @source.s03(mkctx(@source.extract_fenced_code(doc)))
  inspect(fs.length(), content="1")
  inspect(fs[0].line, content="3")
}

///|
test "prose only mbt.md yields no findings" {
  let doc = "we discuss curl and @shell.Cmd in prose\nwith no fences at all\n"
  let fs = @source.s03(mkctx(@source.extract_fenced_code(doc)))
  inspect(fs.length(), content="0")
}
