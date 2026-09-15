///|
pub(all) enum Severity {
  Low
  Medium
  High
  Critical
} derive(Eq, Debug, ToJson)

///|
pub fn Severity::weight(self : Severity) -> Int {
  match self {
    Low => 1
    Medium => 5
    High => 10
    Critical => 25
  }
}

///|
pub fn Severity::rank(self : Severity) -> Int {
  match self {
    Low => 0
    Medium => 1
    High => 2
    Critical => 3
  }
}

///|
pub fn parse_severity(s : String) -> Severity? {
  match s.to_lower() {
    "low" => Some(Low)
    "medium" => Some(Medium)
    "high" => Some(High)
    "critical" => Some(Critical)
    _ => None
  }
}

///|
pub(all) enum Category {
  Metadata
  Source
} derive(Eq, Debug, ToJson)

///|
pub(all) struct Finding {
  rule : String
  severity : Severity
  category : Category
  file : String
  line : Int
  snippet : String
  message : String
} derive(Debug, ToJson)

///|
pub(all) struct RuleDef {
  id : String
  severity : Severity
  category : Category
  description : String
} derive(Debug, ToJson)

///|
pub fn RuleDef::finding(
  self : RuleDef,
  file~ : String,
  line~ : Int,
  snippet~ : String,
  message~ : String,
) -> Finding {
  {
    rule: self.id,
    severity: self.severity,
    category: self.category,
    file,
    line,
    snippet,
    message,
  }
}

///|
/// 供字符串插值/终端输出使用的领域文本形式（Severity 不 derive Show）
pub fn Severity::label(self : Severity) -> String {
  match self {
    Low => "Low"
    Medium => "Medium"
    High => "High"
    Critical => "Critical"
  }
}
