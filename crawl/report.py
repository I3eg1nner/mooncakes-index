import json
import os
import sys
from collections import defaultdict

VERDICT_ORDER = ("Malicious", "Suspicious", "Error", "Clean")


def load_rows(results_path: str) -> list[dict]:
    """Parse a JSONL results file: skip malformed lines (with a stderr
    warning) and dedup by module, last row winning (a crash between the
    results append and state.mark re-scans a module on resume)."""
    rows: list[dict] = []
    malformed = 0
    with open(results_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                malformed += 1
    if malformed:
        print(f"warning: skipped {malformed} malformed result line(s)", file=sys.stderr)
    dedup: dict[str, dict] = {}
    for r in rows:
        dedup[r.get("module") or ""] = r
    return list(dedup.values())


def write_summary(results_path: str, out_path: str) -> None:
    rows = load_rows(results_path)
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        groups[r.get("verdict", "Error")].append(r)
    n = len(rows)
    directory = os.path.dirname(out_path) or "."
    os.makedirs(directory, exist_ok=True)
    with open(out_path, "w") as out:
        out.write(f"# mooncakes.io audit summary\n\nscanned: {n}\n\n")
        for verdict in VERDICT_ORDER + tuple(sorted(set(groups) - set(VERDICT_ORDER))):
            rows = groups.get(verdict, [])
            out.write(f"## {verdict} ({len(rows)})\n\n")
            if verdict == "Clean":
                continue
            out.write("| module | version | risk | findings |\n|---|---|---|---|\n")
            for r in sorted(rows, key=lambda r: -r.get("risk", 0)):
                rules = ",".join(sorted({f["rule"] for f in r.get("findings", []) if "rule" in f}))
                err = r.get("error", "")
                detail = rules or err
                out.write(f"| {r.get('module')} | {r.get('version', '')} | {r.get('risk', '')} | {detail} |\n")
            out.write("\n")
