///|
fn manifest(
  name : String,
  repo : String,
  deps : Array[String],
) -> @metadata.Manifest {
  { name, version: "0.1.0", repository: repo, readme: "README.md", deps }
}

///|
test "m02 impersonation of official" {
  let fs = @metadata.m02(
    manifest("evil/core", "https://github.com/evil/core", []),
  )
  inspect(fs.length(), content="1")
  debug_inspect(fs[0].severity, content="Critical")
  inspect(fs[0].rule, content="M02")
  inspect(
    @metadata.m02(
      manifest("moonbitlang/core", "https://github.com/moonbitlang/core", []),
    ).length(),
    content="0",
  )
}

///|
test "m01 typosquat" {
  let hot = ["moonbitlang/async", "moonbitlang/core", "rxml/moonbit-xml"]
  let fs = @metadata.m01(
    manifest("evil/asynx", "https://github.com/evil/asynx", []),
    hot,
  )
  inspect(fs.length(), content="1")
  debug_inspect(fs[0].severity, content="High")
  inspect(fs[0].rule, content="M01")
  // exact repo-name match is skipped, not reported
  inspect(
    @metadata.m01(
      manifest("moonbitlang/async", "https://github.com/moonbitlang/async", []),
      hot,
    ).length(),
    content="0",
  )
  // DL("typo-async", "async") = 5 > 2 -> no finding
  inspect(
    @metadata.m01(
      manifest("evil/typo-async", "https://github.com/evil/typo-async", []),
      hot,
    ).length(),
    content="0",
  )
}

///|
test "m03 empty shell" {
  let fs = @metadata.m03(
    manifest("a/great-lib", "https://github.com/a/great-lib", []),
    50,
    false,
  )
  inspect(fs.length(), content="1")
  debug_inspect(fs[0].severity, content="Medium")
  inspect(fs[0].rule, content="M03")
  inspect(
    @metadata.m03(
      manifest("a/great-lib", "https://github.com/a/great-lib", []),
      5000,
      true,
    ).length(),
    content="0",
  )
}

///|
test "m04 repo owner mismatch" {
  let fs = @metadata.m04(
    manifest("author1/lib", "https://github.com/otherowner/lib", []),
  )
  inspect(fs.length(), content="1")
  debug_inspect(fs[0].severity, content="Medium")
  inspect(fs[0].rule, content="M04")
  let low = @metadata.m04(manifest("a/lib", "", []))
  inspect(low.length(), content="1")
  debug_inspect(low[0].severity, content="Low")
  // matching owner -> no finding
  inspect(
    @metadata.m04(manifest("a/lib", "https://github.com/a/lib", [])).length(),
    content="0",
  )
}

///|
test "m05 dependency confusion" {
  let hot = ["moonbitlang/async", "bobzhang/toml"]
  let fs = @metadata.m05(
    manifest("a/lib", "https://github.com/a/lib", ["bobzhang/tonml"]),
    hot,
  )
  inspect(fs.length(), content="1")
  debug_inspect(fs[0].severity, content="High")
  inspect(fs[0].rule, content="M05")
  inspect(fs[0].snippet, content="bobzhang/tonml")
  // exact matches (hotlist + official names) are excluded
  let none = @metadata.m05(
    manifest("a/lib", "https://github.com/a/lib", [
      "moonbitlang/async", "moonbitlang/x",
    ]),
    hot,
  )
  inspect(none.length(), content="0")
}

///|
test "name/url segment helpers" {
  inspect(
    @metadata.repo_of_url("https://github.com/evil/core/"),
    content="core",
  )
  inspect(@metadata.repo_of_url("not-a-url"), content="")
  inspect(@metadata.official_repo_names().length(), content="6")
  // trailing slash on repository URL still resolves owner == author
  inspect(
    @metadata.m04(manifest("a/lib", "https://github.com/a/lib/", [])).length(),
    content="0",
  )
}
