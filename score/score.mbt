///|
pub(all) enum Verdict {
  Clean
  Suspicious
  Malicious
} derive(Eq, Debug)

///|
pub fn Verdict::to_string(self : Verdict) -> String {
  match self {
    Clean => "Clean"
    Suspicious => "Suspicious"
    Malicious => "Malicious"
  }
}

///|
/// `risk >= 50` → Malicious; `risk >= 15` → Suspicious; otherwise Clean.
pub fn verdict_of(risk : Int) -> Verdict {
  if risk >= 50 {
    Malicious
  } else if risk >= 15 {
    Suspicious
  } else {
    Clean
  }
}

///|
/// Aggregate risk: per rule keep the highest-severity finding, sum weights,
/// cap at 100.
pub fn risk_of(findings : Array[@engine.Finding]) -> Int {
  let per_rule : Map[String, @engine.Severity] = Map([])
  for f in findings {
    match per_rule.get(f.rule) {
      Some(s) =>
        if f.severity.rank() > s.rank() {
          per_rule[f.rule] = f.severity
        }
      None => per_rule[f.rule] = f.severity
    }
  }
  let mut total = 0
  for _, sev in per_rule {
    total += sev.weight()
  }
  if total > 100 {
    100
  } else {
    total
  }
}
