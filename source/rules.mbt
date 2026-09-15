///|
pub fn all_source_rules() -> Array[
  (String, (SourceCtx) -> Array[@engine.Finding]),
] {
  [
    ("S01", s01),
    ("S02", s02),
    ("S03", s03),
    ("S04", s04),
    ("S05", s05),
    ("S07", s07),
    ("S08", s08),
  ]
}
