# Canary fixtures

Fixed sample packages pinned by `engine/scan/e2e_test.mbt`; each asserts a
verdict through the full `run_scan` pipeline (walk → metadata/source rules →
scoring).

- `typo_malicious` (`eviluser/asynx`): typosquat of a hotlisted module plus
  credential read + raw-IP exfil URL → M01 + S01 + S02 + S99 + M03 + M04 = 61,
  Malicious.
- `prebuild_dropper` (`eviluser/build-helper`): `pre-build` hook that pipes
  `curl` into `sh`, plus a source-level `@shell.Cmd("curl", ...)` → S06 + S03
  + S01 + M03 + M04 = 66, Malicious.
- `obfuscated_exfil` (`eviluser/obfz`): >80-char base64 blob decoded at
  runtime → S04 (High; blob and decode call collapse to max severity) + M03 +
  M04 = 16, Suspicious.
- `benign_http` (`goodorg/http-client-demo`): ordinary HTTPS demo client with
  repository field and substantial README → risk 0, Clean (zero false
  positives).

These directories are committed fixtures, not runtime artifacts; each has its
own `moon.mod` so the build never compiles them.
