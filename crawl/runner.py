import json
import subprocess


def scan_package(
    engine_bin: str,
    pkg_dir: str,
    hotlist: str | None,
    timeout: int = 60,
    module: str | None = None,
    version: str | None = None,
) -> dict:
    cmd = [engine_bin, "scan", pkg_dir, "--json"]
    if hotlist:
        cmd += ["--hotlist", hotlist]
    if module:
        cmd += ["--module", module]
    if version:
        cmd += ["--version", version]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"module": pkg_dir, "error": "timeout"}
    except OSError as e:
        return {"module": pkg_dir, "error": f"engine not runnable: {e}"}
    for line in reversed(p.stdout.strip().splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except json.JSONDecodeError as e:
                return {"module": pkg_dir, "error": f"bad json from engine: {e}"}
    return {"module": pkg_dir, "error": f"exit {p.returncode}: {p.stderr[-200:]}"}
