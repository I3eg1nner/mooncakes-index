///|
async test "run_scan over temp malicious dir" {
  let dir = @fs.tmpdir(prefix="scan-test-")
  @fs.mkdir(dir + "/src", recursive=true)
  @fs.write_file(
    dir + "/moon.mod",
    "name = \"evil/asynx\"\nversion = \"0.1.0\"\n",
    create_mode=CreateOrTruncate,
  )
  @fs.write_file(
    dir + "/src/a.mbt",
    "let p = \"/home/u/.ssh/id_rsa\"\nlet c = @fs.read_file_to_string(p)",
    create_mode=CreateOrTruncate,
  )
  let r = @scan.run_scan(dir, {
    hotlist: ["moonbitlang/async", "moonbitlang/core"],
  })
  inspect(r.module, content="evil/asynx")
  // M01(10) + S02(10) = 20 → Suspicious
  inspect(r.verdict, content="Suspicious")
  let rules = r.findings.map(f => f.rule)
  rules.sort()
  inspect(rules.contains("M01") && rules.contains("S02"), content="true")
  // metadata findings carry "moon.mod"; source findings carry relative paths
  inspect(
    r.findings.iter().any(f => f.rule == "M01" && f.file == "moon.mod"),
    content="true",
  )
  inspect(
    r.findings.iter().any(f => f.rule == "S02" && f.file == "src/a.mbt"),
    content="true",
  )
}

///|
async test "run_scan without moon.mod falls back to dir name" {
  let dir = @fs.tmpdir(prefix="scan-empty-")
  @fs.mkdir(dir + "/src", recursive=true)
  @fs.write_file(
    dir + "/src/empty.mbt",
    "let x = 1\n",
    create_mode=CreateOrTruncate,
  )
  let r = @scan.run_scan(dir, { hotlist: [] })
  let dirname = match dir.rev_find("/") {
    Some(i) => dir[i + 1:].to_owned()
    None => dir
  }
  inspect(r.module == dirname, content="true")
  inspect(r.version, content="")
  inspect(r.errors.contains("cannot parse moon.mod"), content="true")
  inspect(r.verdict, content="Clean")
  inspect(r.risk, content="0")
}

///|
async test "run_scan survives symlink loop" {
  let dir = @fs.tmpdir(prefix="scan-symlink-")
  @fs.write_file(
    dir + "/moon.mod",
    "name = \"evil/loop\"\nversion = \"0.1.0\"\n",
    create_mode=CreateOrTruncate,
  )
  // directory symlink cycle: loop -> . would recurse forever pre-fix
  @fs.symlink(target=".", dir + "/loop")
  let r = @scan.run_scan(dir, { hotlist: [] })
  inspect(r.module, content="evil/loop")
  inspect(r.verdict, content="Clean")
  inspect(r.errors.length(), content="0")
}

///|
async test "run_scan reads moon.mod.json fallback" {
  let dir = @fs.tmpdir(prefix="scan-modjson-")
  @fs.mkdir(dir + "/src", recursive=true)
  @fs.write_file(
    dir + "/moon.mod.json",
    "{\"name\": \"a/b\", \"version\": \"1.0.0\", \"repository\": \"https://github.com/a/b\"}",
    create_mode=CreateOrTruncate,
  )
  @fs.write_file(
    dir + "/src/a.mbt",
    "let x = 1\n",
    create_mode=CreateOrTruncate,
  )
  let r = @scan.run_scan(dir, { hotlist: [] })
  inspect(r.module, content="a/b")
  inspect(r.version, content="1.0.0")
  inspect(r.errors.contains("cannot parse moon.mod"), content="false")
}

///|
async test "run_scan applies s-rules to mbt.md fences only" {
  let dir = @fs.tmpdir(prefix="scan-mbtmd-")
  @fs.mkdir(dir + "/src", recursive=true)
  @fs.write_file(
    dir + "/moon.mod",
    "name = \"evil/docfp\"\nversion = \"0.1.0\"\n",
    create_mode=CreateOrTruncate,
  )
  @fs.write_file(
    dir + "/src/doc.mbt.md",
    "prose mentions system(\"curl http://x\") in passing\n```\nsystem(\"curl http://x\")\n```\n",
    create_mode=CreateOrTruncate,
  )
  let r = @scan.run_scan(dir, { hotlist: [] })
  let s03 = r.findings.filter(f => f.rule == "S03")
  inspect(s03.length(), content="1")
  inspect(s03[0].file, content="src/doc.mbt.md")
  inspect(s03[0].line, content="3")
}
