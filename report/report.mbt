///|
pub(all) struct Report {
  module : String
  version : String
  risk : Int
  verdict : String
  findings : Array[@engine.Finding]
  errors : Array[String]
} derive(Debug, ToJson)

///|
pub fn Report::to_json_string(self : Report) -> String {
  self.to_json().stringify()
}

///|
pub fn human_summary(r : Report) -> String {
  let sb = StringBuilder()
  sb <+ "module: \{r.module}@\{r.version}\n"
  sb <+ "risk: \{r.risk} verdict: \{r.verdict}\n"
  sb <+ "findings: \{r.findings.length()} errors: \{r.errors.length()}\n"
  for f in r.findings {
    sb <+
      "  [\{f.rule}/\{f.severity.label()}] \{f.file}:\{f.line} \{f.message}\n"
  }
  sb.to_string()
}
