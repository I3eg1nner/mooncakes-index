///|
test "line index and snippet" {
  let s = "aaa\nbbbb\ncc"
  let li = @matchers.LineIndex::build(s)
  inspect(li.line_of(0), content="1")
  inspect(li.line_of(4), content="2")
  inspect(li.line_of(9), content="3")
  inspect(li.snippet(s, 2), content="bbbb")
}

///|
test "raw ip url" {
  inspect(@matchers.is_raw_ip_url("http://192.168.1.1/x"), content="true")
  inspect(@matchers.is_raw_ip_url("http://evil.example.com/x"), content="false")
  inspect(@matchers.is_raw_ip_url("https://10.0.0.1:8080/post"), content="true")
}

///|
test "longest run" {
  // 96 字符 base64 安全字集
  let blob = "Ab0Cd1Ef2Gh3Ij4Kl5Mn6Op7Qr8St9Uv0Wx1Yz2Ab3Cd4Ef5Gh6Ij7Kl8Mn9Op0Qr1St2Uv3Wx4Yz5Ab6Cd7Ef8Gh9Ij0Kl1"
  inspect(blob.length(), content="96")
  inspect(@matchers.longest_run(blob, @matchers.is_b64), content="96")
  inspect(@matchers.longest_run("abc123", @matchers.is_hex), content="6")
  inspect(@matchers.longest_run("abcg", @matchers.is_hex), content="3")
}

///|
test "damerau levenshtein" {
  inspect(@matchers.damerau_levenshtein("asyncx", "async"), content="1")
  inspect(@matchers.damerau_levenshtein("asynx", "async"), content="1")
  inspect(@matchers.damerau_levenshtein("abc", "abc"), content="0")
  inspect(@matchers.damerau_levenshtein("kitten", "sitting"), content="3")
  inspect(@matchers.damerau_levenshtein("ab", "ba"), content="1")
}
