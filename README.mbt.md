# mooncake-audit

Supply-chain security auditor for [mooncakes.io](https://mooncakes.io) packages, written in MoonBit with a Python crawl orchestrator.

A native scan engine statically analyzes package sources and manifests for typo-squatting, prebuild/install hooks, network/process/file-system abuse and obfuscation, and emits per-module findings with a risk score and verdict (Malicious / Suspicious / Clean).

## Build

Requires the MoonBit toolchain (`moon`) and Python 3.10+.

```bash
moon check
moon test
moon build --target native --release
```

The engine binary lands at `_build/native/release/build/cmd/main/main.exe`.

```text
usage: mooncake-audit scan <dir> [--module m] [--version v] [--hotlist file] [--json] [--min-severity low|medium|high|critical]
```

## Scan a single package

```bash
moon build --target native --release
ENGINE=$(find _build/native/release -type f -executable | head -1)
mkdir -p /tmp/pkg && unzip moonkafka-0.2.1.zip -d /tmp/pkg
"$ENGINE" scan /tmp/pkg --module daqing/moonkafka --version 0.2.1 --json
```

`--json` prints one machine-readable report; omit it for a human-readable summary. `--min-severity` filters noise, e.g. `--min-severity high`.

## Crawl the registry

The Python orchestrator downloads packages from mooncakes.io (rate-limited, zip-slip-safe extraction), scans each with the engine, and appends results.

Build the hotlist first — the top-N most prominent modules, used by the engine's typo-squatting rules:

```bash
python3 -m crawl.hotlist --out state/hotlist.txt --top 100
```

Sampled pilot run (first 50 modules of the registry index):

```bash
python3 -m crawl.crawl --engine "$ENGINE" --modules sample:50
python3 -c "from crawl.report import write_summary; write_summary('results/results.jsonl','results/summary.md')"
```

Full crawl of every module in the registry:

```bash
python3 -m crawl.crawl --engine "$ENGINE" --modules all
python3 -c "from crawl.report import write_summary; write_summary('results/results.jsonl','results/summary.md')"
```

Useful flags:

- `--modules all | sample:N | file:LIST` — module selection (`file:` filters the index to names listed in a file)
- `--hotlist state/hotlist.txt` — typo-squat target list passed to the engine (default)
- `--workers N --rate SECONDS` — parallelism and per-request rate limit
- `--state/--corpus/--results` — state file, package cache and output paths (defaults under `state/`, `corpus/`, `results/`)

Only each module's latest version is scanned in v1 (`--all-versions` is a possible future extension).

### Resuming

Crawl progress is checkpointed in `state/crawl_state.json`. Re-running the same command skips modules already marked done, so a full crawl interrupted midway resumes where it left off. Delete the state file to start over.

### Artifacts

- `results/results.jsonl` — one JSON report per module (verdict, risk score, findings)
- `results/summary.md` — grouped summary: Malicious / Suspicious / Error counts with per-module findings, Clean count

`state/`, `corpus/`, `results/` and `.repos/` are gitignored.

## Development

- Engine: MoonBit under `engine/`, `metadata/`, `cmd/` — `moon test` runs the rule and canary-package suites
- Orchestrator: `crawl/` — `python3 -m pytest crawl/ -v`
