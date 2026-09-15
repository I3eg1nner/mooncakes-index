///|
test "severity weight and rank" {
  inspect(@engine.Low.weight(), content="1")
  inspect(@engine.Medium.weight(), content="5")
  inspect(@engine.High.weight(), content="10")
  inspect(@engine.Critical.weight(), content="25")
  inspect(@engine.Low.rank() < @engine.High.rank(), content="true")
}

///|
test "severity parse" {
  debug_inspect(@engine.parse_severity("high"), content="Some(High)")
  debug_inspect(@engine.parse_severity("nope"), content="None")
}

///|
test "finding to_json" {
  let f : @engine.Finding = {
    rule: "S02",
    severity: @engine.High,
    category: @engine.Source,
    file: "src/a.mbt",
    line: 3,
    snippet: "read .ssh",
    message: "credential access",
  }
  json_inspect(f, content={
    "rule": "S02",
    "severity": "High",
    "category": "Source",
    "file": "src/a.mbt",
    "line": 3,
    "snippet": "read .ssh",
    "message": "credential access",
  })
}
