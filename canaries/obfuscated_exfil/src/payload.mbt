///|
let payload : String =
  "aGVsbG8gd29ybGQgdGhpcyBpcyBhIHZlcnkgbG9uZyBiYXNlNjQgYmxvYiBmb3IgdGVzdGluZyBwdXJwb3NlcyBvbmx5IG5vdCByZWFs"

///|
fn decode_and_run() -> String {
  payload.from_base64()
}
