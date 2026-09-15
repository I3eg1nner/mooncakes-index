///|
let cred_patterns : Array[String] = [
  ".ssh", "id_rsa", "id_ed25519", ".aws", "credentials", ".npmrc", ".netrc", "authorized_keys",
  "keystore", "keychain", ".git-credentials", "wallet.dat",
]

///|
let read_indicators : Array[String] = [
  "read_file", "read_dir", "read_file_to_string", "@fs.open", "File::open", "read_to_string",
]

///|
let cred_ac : @matchers.Automaton = @matchers.Automaton::new(cred_patterns)

///|
pub fn s02(ctx : SourceCtx) -> Array[@engine.Finding] {
  let hits = dedupe_by_line(cred_ac.scan(ctx.content), ctx.lines)
  if hits.length() == 0 {
    return []
  }
  let has_read = contains_any(ctx.content, read_indicators)
  let sev = if has_read { @engine.High } else { @engine.Low }
  findings_for(
    ctx,
    "S02",
    severity=sev,
    hits,
    if has_read {
      "credential path read"
    } else {
      "credential path reference"
    },
  )
}
