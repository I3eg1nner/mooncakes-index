///|
test "s07 env sniffing threshold" {
  let two = "let a = @env.get_env_var(\"API_KEY\")\nlet b = @env.get_env_var(\"SECRET\")"
  let fs = @source.s07(@source.mkctx_for_test(two))
  inspect(fs.length(), content="1")
  inspect(fs[0].rule, content="S07")
  debug_inspect(fs[0].severity, content="Medium")
  let four = "let a = @env.get_env_var(\"API_KEY\")\nlet b = @env.get_env_var(\"SECRET\")\nlet c = @env.get_env_var(\"TOKEN\")\nlet d = @env.get_env_var(\"PASSWORD\")"
  let fs4 = @source.s07(@source.mkctx_for_test(four))
  inspect(fs4.length(), content="1")
  debug_inspect(fs4[0].severity, content="High")
}

///|
test "s07 requires env call and two keyword classes" {
  // 敏感键但无 env 调用指示：不报
  let noenv = "let a = \"API_KEY\"\nlet b = \"SECRET\""
  inspect(@source.s07(@source.mkctx_for_test(noenv)).length(), content="0")
  // env 调用但仅 1 类敏感键：不报
  let one = "let a = @env.get_env_var(\"API_KEY\")"
  inspect(@source.s07(@source.mkctx_for_test(one)).length(), content="0")
}

///|
test "s08 ssh write is critical" {
  let code = "@fs.write_string_to_file(\"/root/.ssh/authorized_keys\", my_key)"
  let fs = @source.s08(@source.mkctx_for_test(code))
  inspect(fs.length(), content="1")
  inspect(fs[0].rule, content="S08")
  debug_inspect(fs[0].severity, content="Critical")
  inspect(fs[0].file, content="src/x.mbt")
}

///|
test "s08 no write call or benign target" {
  // 敏感目标但无写调用：不报
  let nowrite = "let x = \"/root/.ssh/authorized_keys\""
  inspect(@source.s08(@source.mkctx_for_test(nowrite)).length(), content="0")
  // 写调用但目标不敏感：不报
  let benign = "@fs.write_string_to_file(\"/tmp/log.txt\", data)"
  inspect(@source.s08(@source.mkctx_for_test(benign)).length(), content="0")
}
