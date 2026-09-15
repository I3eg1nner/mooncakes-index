///|
/// End-to-end canary fixtures (see canaries/README.md): each fixture pins a
/// slice of the scoring model through the full run_scan pipeline.

///|
fn canary(name : String) -> String {
  "canaries/" + name
}

///|
async test "canary typo_malicious is malicious" {
  let r = @scan.run_scan(canary("typo_malicious"), {
    hotlist: ["moonbitlang/async"],
  })
  // M01(10)+S01(10)+S02(10)+S99(25)+M03(5)+M04(1) = 61
  inspect(r.risk >= 50, content="true")
  inspect(r.verdict, content="Malicious")
}

///|
async test "canary prebuild_dropper is malicious" {
  let r = @scan.run_scan(canary("prebuild_dropper"), { hotlist: [] })
  // S06(25)+S03(25)+S01(10)+M03(5)+M04(1) = 66
  inspect(r.risk >= 50, content="true")
  inspect(r.verdict, content="Malicious")
}

///|
async test "canary obfuscated_exfil is suspicious" {
  let r = @scan.run_scan(canary("obfuscated_exfil"), { hotlist: [] })
  // S04 High(10) (blob+decode collapse to max severity) + M03(5) + M04(1) = 16
  inspect(r.risk >= 15, content="true")
  inspect(r.verdict, content="Suspicious")
}

///|
async test "canary benign_http is clean" {
  let r = @scan.run_scan(canary("benign_http"), {
    hotlist: ["moonbitlang/async"],
  })
  inspect(r.risk, content="0")
  inspect(r.verdict, content="Clean")
}
