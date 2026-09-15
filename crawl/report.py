import json
import os
from collections import defaultdict

VERDICT_ORDER = ("Malicious", "Suspicious", "Error", "Clean")


def write_summary(results_path: str, out_path: str) -> None:
    groups: dict[str, list[dict]] = defaultdict(list)
    n = 0
    with open(results_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            n += 1
            groups[r.get("verdict", "Error")].append(r)
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
