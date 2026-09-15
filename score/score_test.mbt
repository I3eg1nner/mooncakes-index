///|
fn f(rule : String, sev : @engine.Severity) -> @engine.Finding {
  {
    rule,
    severity: sev,
    category: @engine.Source,
    file: "a.mbt",
    line: 1,
    snippet: "",
    message: "",
  }
}

///|
test "risk aggregates per rule max" {
  let fs = [
    f("S02", @engine.High),
    f("S02", @engine.High),
    f("S04", @engine.Medium),
  ]
  inspect(@score.risk_of(fs), content="15")
}

///|
test "risk caps at 100" {
  let fs : Array[@engine.Finding] = []
  for i in 0..<10 {
    fs.push(f("S0\{i}", @engine.Critical))
  }
  inspect(@score.risk_of(fs), content="100")
}

///|
test "verdict thresholds" {
  inspect(@score.verdict_of(0).to_string(), content="Clean")
  inspect(@score.verdict_of(14).to_string(), content="Clean")
  inspect(@score.verdict_of(15).to_string(), content="Suspicious")
  inspect(@score.verdict_of(49).to_string(), content="Suspicious")
  inspect(@score.verdict_of(50).to_string(), content="Malicious")
}
