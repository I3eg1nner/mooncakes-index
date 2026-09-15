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
test "m02 authoritative name closes manifest-name spoofing" {
  // 注册为 evil/asynx，manifest 声明 name = "moonbitlang/async"：
  // 无权威名时 author 早退（旧漏洞）；有权威名时 author 取 evil → 命中官方 repo 集
  inspect(
    @metadata.m02(
      manifest("moonbitlang/async", "https://github.com/moonbitlang/async", []),
    ).length(),
    content="0",
  )
  let fs = @metadata.m02(
    manifest("moonbitlang/async", "https://github.com/moonbitlang/async", []),
    authoritative="evil/asynx",
  )
  inspect(fs.length(), content="1")
  debug_inspect(fs[0].severity, content="Critical")
  // 权威名自身仿冒官方 repo（evil/core）也命中
  inspect(
    @metadata.m02(
      manifest("evil/whatever", "https://github.com/evil/whatever", []),
      authoritative="evil/core",
    ).length(),
    content="1",
  )
  // 权威名为正版 moonbitlang/*：不报
  inspect(
    @metadata.m02(
      manifest("moonbitlang/async", "https://github.com/moonbitlang/async", []),
      authoritative="moonbitlang/async",
    ).length(),
    content="0",
  )
}

///|
test "m02 official repo comparison is case insensitive" {
  // repo "Core" 与官方 "core" 仅大小写不同 → 仍视为仿冒
  inspect(
    @metadata.m02(manifest("evil/Core", "https://github.com/evil/Core", [])).length(),
    content="1",
  )
}

///|
test "m01 authoritative name participates in typosquat comparison" {
  let hot = ["moonbitlang/async"]
  // 声明名 "moonbitlang/async" 与 hotlist 精确同名 → 旧逻辑跳过；
  // 权威名 evil/asynx 的 repo "asynx" DL(async)=1 → 报
  inspect(
    @metadata.m01(
      manifest("moonbitlang/async", "https://github.com/moonbitlang/async", []),
      hot,
    ).length(),
    content="0",
  )
  let fs = @metadata.m01(
    manifest("moonbitlang/async", "https://github.com/moonbitlang/async", []),
    hot,
    authoritative="evil/asynx",
  )
  inspect(fs.length(), content="1")
  debug_inspect(fs[0].severity, content="High")
  inspect(fs[0].snippet, content="evil/asynx")
}

///|
test "m04 authoritative author vs repository owner" {
  // 声明名伪装使 owner 与 author 恰好一致；权威名揭示真实 author 为 evil
  inspect(
    @metadata.m04(
      manifest("moonbitlang/async", "https://github.com/moonbitlang/async", []),
    ).length(),
    content="0",
  )
  let fs = @metadata.m04(
    manifest("moonbitlang/async", "https://github.com/moonbitlang/async", []),
    authoritative="evil/asynx",
  )
  inspect(fs.length(), content="1")
  debug_inspect(fs[0].severity, content="Medium")
  // 权威名与 owner 一致时不报
  inspect(
    @metadata.m04(
      manifest("whatever/declared", "https://github.com/evil/real", []),
      authoritative="evil/real",
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
test "m01 short repo names skip dl comparison" {
  // 双方 repo 名长度 < 5 时短名碰撞过于随机（json/jsoo、elk/pkl）→ 不比对
  inspect(
    @metadata.m01(manifest("b/jsoo", "https://github.com/b/jsoo", []), [
      "a/json",
    ]).length(),
    content="0",
  )
  // 双方 repo 名均 ≥ 5 时照常比对（asynx/async，DL=1）
  inspect(
    @metadata.m01(manifest("evil/asynx", "https://github.com/evil/asynx", []), [
      "moonbitlang/async",
    ]).length(),
    content="1",
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
test "m04 owner comparison is case insensitive" {
  // GitHub 登录名大小写不敏感：Foo/foo 视为同一 owner
  inspect(
    @metadata.m04(manifest("Foo/lib", "https://github.com/foo/lib", [])).length(),
    content="0",
  )
  // 大小写之外确有差异时仍报
  inspect(
    @metadata.m04(manifest("Foo/lib", "https://github.com/other/lib", [])).length(),
    content="1",
  )
}

///|
test "m05 dependency confusion" {
  let hot = ["moonbitlang/async", "rxml/moonbit-xml"]
  let fs = @metadata.m05(
    manifest("a/lib", "https://github.com/a/lib", ["rxml/moonbit-xmk"]),
    hot,
  )
  inspect(fs.length(), content="1")
  debug_inspect(fs[0].severity, content="High")
  inspect(fs[0].rule, content="M05")
  inspect(fs[0].snippet, content="rxml/moonbit-xmk")
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
test "m05 short repo names skip dl comparison" {
  // 依赖 repo "x"（<5）与 hotlist 短名 "ts" 碰撞 → 不报
  inspect(
    @metadata.m05(
      manifest("a/lib", "https://github.com/a/lib", ["moonbitlang/x"]),
      ["mizchi/ts"],
    ).length(),
    content="0",
  )
  // 官方名集合含单字母 "x"：短 repo "y" 的碰撞同样不报
  inspect(
    @metadata.m05(
      manifest("a/lib", "https://github.com/a/lib", ["moonbitlang/y"]),
      [],
    ).length(),
    content="0",
  )
  // 双方 repo 名均 ≥5 的真实近似仍报
  inspect(
    @metadata.m05(
      manifest("a/lib", "https://github.com/a/lib", ["moonbitlang/asynx"]),
      ["moonbitlang/async"],
    ).length(),
    content="1",
  )
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
