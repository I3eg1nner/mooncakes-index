///|
let decode_calls : Array[String] = [
  "from_base64", "decode_base64", "base64::decode", "atob", "hex::decode",
]

///|
pub fn s04(ctx : SourceCtx) -> Array[@engine.Finding] {
  let fs : Array[@engine.Finding] = []
  let rd_hi : @engine.RuleDef = {
    id: "S04",
    severity: @engine.High,
    category: @engine.Source,
    description: "encoded blob",
  }
  let rd_md : @engine.RuleDef = {
    id: "S04",
    severity: @engine.Medium,
    category: @engine.Source,
    description: "decode call",
  }
  let rd_lo : @engine.RuleDef = {
    id: "S04",
    severity: @engine.Low,
    category: @engine.Source,
    description: "hex run",
  }
  let (b64, b64_at) = longest_run_at(ctx.content, @matchers.is_b64)
  let (hex, hex_at) = longest_run_at(ctx.content, @matchers.is_hex)
  if b64 > 80 {
    let line = ctx.lines.line_of(b64_at)
    fs.push(
      rd_hi.finding(
        file=ctx.file,
        line~,
        snippet=ctx.lines.snippet(ctx.content, line),
        message="base64 blob length \{b64}",
      ),
    )
  }
  if hex >= 64 {
    let line = ctx.lines.line_of(hex_at)
    fs.push(
      rd_lo.finding(
        file=ctx.file,
        line~,
        snippet=ctx.lines.snippet(ctx.content, line),
        message="hex run length \{hex} (possibly crypto constants)",
      ),
    )
  }
  for p in decode_calls {
    match ctx.content.find(p) {
      Some(off) => {
        let line = ctx.lines.line_of(off)
        fs.push(
          rd_md.finding(
            file=ctx.file,
            line~,
            snippet=ctx.lines.snippet(ctx.content, line),
            message="decoding call \"\{p}\"",
          ),
        )
      }
      None => ()
    }
  }
  fs
}
