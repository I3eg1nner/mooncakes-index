///|
fn mkctx(content : String) -> @source.SourceCtx {
  { file: "src/x.mbt", content, lines: @matchers.LineIndex::build(content) }
}

///|
test "S01 network exfil raw ip" {
  let fs = @source.s01(mkctx("let u = \"http://13.37.13.37/upload\""))
  inspect(fs.length(), content="1")
  debug_inspect(fs[0].severity, content="High")
  inspect(fs[0].rule, content="S01")
}

///|
test "S01 clean code no high finding" {
  let fs = @source.s01(mkctx("let x = @http.get(\"https://api.github.com\")"))
  for f in fs {
    inspect(f.severity.rank() < @engine.High.rank(), content="true")
  }
}

///|
test "S02 credential read combo" {
  let fs = @source.s02(
    mkctx("let c = @fs.read_file_to_string(\"/home/u/.ssh/id_rsa\")"),
  )
  inspect(fs.length(), content="1")
  debug_inspect(fs[0].severity, content="High")
}

///|
test "S02 keyword only is low" {
  let fs = @source.s02(mkctx("// TODO handle .npmrc later"))
  inspect(fs.length(), content="1")
  debug_inspect(fs[0].severity, content="Low")
}

///|
test "S02 finding line populated" {
  let fs = @source.s02(mkctx("fn a() {\n  // .npmrc\n}"))
  inspect(fs.length(), content="1")
  inspect(fs[0].file, content="src/x.mbt")
  inspect(fs[0].line, content="2")
  inspect(fs[0].snippet, content="  // .npmrc")
}

///|
test "S03 spawn with curl is critical" {
  let fs = @source.s03(
    mkctx("@shell.Cmd(\"curl\", [\"http://x/y\"]) |> ignore"),
  )
  debug_inspect(fs[0].severity, content="Critical")
}

///|
test "S03 plain spawn is medium" {
  let fs = @source.s03(mkctx("@shell.Cmd(\"ls\", [\"-la\"]) |> ignore"))
  debug_inspect(fs[0].severity, content="Medium")
}

///|
test "S03 task spawn is not process execution" {
  let fs = @source.s03(mkctx("let g = @gen.Gen::spawn(() => 1)"))
  inspect(fs.length(), content="0")
}

///|
test "S01 raw ip localhost url is not flagged" {
  let fs = @source.s01(mkctx("let u = \"http://127.0.0.1:8080/test\""))
  inspect(fs.length(), content="0")
}

///|
test "S01 private range raw ip still fires" {
  let fs = @source.s01(mkctx("let u = \"http://10.0.0.5/x\""))
  inspect(fs.length(), content="1")
  debug_inspect(fs[0].severity, content="High")
}

///|
test "S03 identifier containing system is not exec" {
  let fs = @source.s03(mkctx("let x = solve_8x8_system(6)"))
  inspect(fs.length(), content="0")
}

///|
test "S03 method call named system is not exec" {
  let fs = @source.s03(mkctx("let c = ClockProvider::system()"))
  inspect(fs.length(), content="0")
}

///|
test "S03 bare libc call is not exec" {
  let fs = @source.s03(mkctx("fn go() { system(\"ls\") }"))
  inspect(fs.length(), content="0")
}

///|
test "S04 long base64 blob without decode context is low" {
  // 编码长串无同文件解码意图 → 仅 Low（加密常量/测试向量常见形态）
  let blob = "A1b2C3d4E5f6G7h8I9j0A1b2C3d4E5f6G7h8I9j0A1b2C3d4E5f6G7h8I9j0A1b2C3d4E5f6G7h8I9j0A1b2C3d4E5f6G7h8I9j0"
  inspect(blob.length() > 80, content="true")
  let fs = @source.s04(mkctx("let a = 1\nlet s = \"\{blob}\""))
  inspect(fs.length(), content="1")
  debug_inspect(fs[0].severity, content="Low")
  inspect(fs[0].line, content="2")
}

///|
test "S04 blob with same-file decode call is high" {
  let blob = "A1b2C3d4E5f6G7h8I9j0A1b2C3d4E5f6G7h8I9j0A1b2C3d4E5f6G7h8I9j0A1b2C3d4E5f6G7h8I9j0A1b2C3d4E5f6G7h8I9j0"
  let fs = @source.s04(
    mkctx("let s = \"\{blob}\"\nfn d() { s.from_base64() |> ignore }"),
  )
  inspect(fs.length(), content="2")
  debug_inspect(fs[0].severity, content="High")
  debug_inspect(fs[1].severity, content="Medium")
}

///|
test "S04 long hex run is low not high" {
  // 长十六进制串在加密代码中是惯用写法（S 盒/轮常量/测试向量），
  // 仅作 Low 提示；混淆的强信号是 base64 长串（High）。
  let hexblob = "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8"
  inspect(hexblob.length() >= 64, content="true")
  let fs = @source.s04(mkctx("let k = \"\{hexblob}\""))
  inspect(fs.length(), content="1")
  debug_inspect(fs[0].severity, content="Low")
}

///|
test "S05 extern ffi" {
  let fs = @source.s05(
    mkctx("fn dlopen(p : String) -> Unit = \"c\" \"dlopen\""),
  )
  inspect(fs.length(), content="2")
  debug_inspect(fs[0].severity, content="Medium")
  debug_inspect(fs[1].severity, content="Critical")
}

///|
test "S05 danger ffi symbol is critical" {
  let fs = @source.s05(
    mkctx("fn sys_call(cmd : String) -> Int = \"c\" \"system\""),
  )
  inspect(fs.length(), content="2")
  debug_inspect(fs[1].severity, content="Critical")
  inspect(fs[1].message, content="dynamic loading/exec symbol \"system\"")
}

///|
test "S05 bare system call site is not ffi danger" {
  let fs = @source.s05(mkctx("let c = ClockProvider::system()"))
  inspect(fs.length(), content="0")
}

///|
test "S05 extern c medium" {
  let fs = @source.s05(mkctx("fn ext_read(p : String) -> Int = \"c\" \"read\""))
  debug_inspect(fs[0].severity, content="Medium")
}

///|
test "S05 prose extern is ignored" {
  let fs = @source.s05(mkctx("/// extern is a keyword in some languages"))
  inspect(fs.length(), content="0")
}

///|
test "S05 ffi declaration form fires medium" {
  let fs = @source.s05(mkctx("fn f() -> Int = \"c\" \"read\""))
  inspect(fs.length(), content="1")
  debug_inspect(fs[0].severity, content="Medium")
}

///|
test "all source rules registry" {
  let rs = @source.all_source_rules()
  inspect(rs.length(), content="7")
  inspect(rs[0].0, content="S01")
  inspect(rs[4].0, content="S05")
  inspect(rs[5].0, content="S07")
  inspect(rs[6].0, content="S08")
}
