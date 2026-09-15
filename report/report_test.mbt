///|
test "report json round shape" {
  let r : @report.Report = {
    module: "a/b",
    version: "0.1.0",
    risk: 10,
    verdict: "Suspicious",
    findings: [],
    errors: [],
  }
  let j = @json.parse(r.to_json_string())
  guard j is Object(obj) else { fail("expected object") }
  guard obj.get("module") is Some(String(m)) else { fail("expected module") }
  inspect(m, content="a/b")
  guard obj.get("risk") is Some(Number(rk, ..)) else { fail("expected risk") }
  inspect(rk, content="10")
}

///|
test "human summary lists findings" {
  let r : @report.Report = {
    module: "a/b",
    version: "0.1.0",
    risk: 15,
    verdict: "Suspicious",
    findings: [
      {
        rule: "S02",
        severity: @engine.High,
        category: @engine.Source,
        file: "src/a.mbt",
        line: 3,
        snippet: "",
        message: "credential access",
      },
    ],
    errors: ["fetch failed"],
  }
  let s = @report.human_summary(r)
  inspect(s.contains("module: a/b@0.1.0"), content="true")
  inspect(s.contains("risk: 15 verdict: Suspicious"), content="true")
  inspect(s.contains("findings: 1 errors: 1"), content="true")
  inspect(
    s.contains("[S02/High] src/a.mbt:3 credential access"),
    content="true",
  )
}
