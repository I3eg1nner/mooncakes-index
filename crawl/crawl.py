import argparse
import concurrent.futures
import glob
import json
import os
import shutil
import sys
import threading

from . import download, registry, runner
from .state import CrawlState

_results_lock = threading.Lock()


def select_modules(index: list[dict], spec: str) -> list[dict]:
    if spec == "all":
        return index
    if spec.startswith("sample:"):
        n = int(spec.split(":")[1])
        return index[:n]
    if spec.startswith("file:"):
        with open(spec[5:]) as f:
            want = {line.strip() for line in f if line.strip()}
        return [m for m in index if m["name"] in want]
    raise SystemExit(f"bad --modules spec: {spec}")


def _has_manifest(pkg_dir: str) -> bool:
    for pattern in ("moon.mod", "moon.mod.json", "*/moon.mod", "*/moon.mod.json"):
        if glob.glob(os.path.join(pkg_dir, pattern)):
            return True
    return False


def staged_extract(data: bytes, dest: str) -> None:
    """Extract an archive into `dest` via a per-pid staging directory.

    A crash mid-extract leaves only the staging dir behind; `dest` either
    does not exist or is a previously completed extraction, so a truncated
    tree can never be scanned and marked done.
    """
    staging = f"{dest}.staging-{os.getpid()}"
    shutil.rmtree(staging, ignore_errors=True)
    try:
        download.safe_extract(data, staging)
        if _has_manifest(dest):
            return  # another run already completed this package
        try:
            os.rename(staging, dest)
            return
        except OSError:
            if _has_manifest(dest):
                return
            raise
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def main() -> None:
    ap = argparse.ArgumentParser(prog="crawl")
    ap.add_argument("--engine", required=True, help="path to mooncake-audit native binary")
    ap.add_argument("--modules", default="sample:50", help="all | sample:N | file:F")
    ap.add_argument("--state", default="state/crawl_state.json")
    ap.add_argument("--corpus", default="corpus")
    ap.add_argument("--results", default="results/results.jsonl")
    ap.add_argument("--hotlist", default=None, help="hotlist file (default: state/hotlist.txt)")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--rate", type=float, default=0.5)
    args = ap.parse_args()

    index = registry.fetch_module_index()
    mods = select_modules(index, args.modules)
    state = CrawlState.load(args.state)
    os.makedirs(os.path.dirname(args.results) or ".", exist_ok=True)
    os.makedirs(args.corpus, exist_ok=True)
    todo = [m for m in mods if not state.done(m["name"])]
    print(f"modules={len(mods)} todo={len(todo)}")

    hotlist_path = args.hotlist or "state/hotlist.txt"
    hotlist = hotlist_path if os.path.exists(hotlist_path) else None
    if args.hotlist is not None and hotlist is None:
        print(f"warning: --hotlist file not found: {args.hotlist}", file=sys.stderr)

    def job(m: dict) -> None:
        name, version = m["name"], m["version"]
        pkg_dir = os.path.join(args.corpus, name)
        try:
            if not _has_manifest(pkg_dir):
                data = registry.fetch_bytes(registry.download_url(name, version), args.rate)
                staged_extract(data, pkg_dir)
            report = runner.scan_package(
                args.engine, pkg_dir, hotlist, module=name, version=version
            )
            report["module"] = name
            report["version"] = version
            status = "fail:scan" if "error" in report else "ok"
        except Exception as e:  # noqa: BLE001
            report = {"module": name, "version": version, "error": str(e)[:200]}
            status = f"fail:{type(e).__name__}"
        with _results_lock:
            with open(args.results, "a") as f:
                f.write(json.dumps(report, ensure_ascii=False) + "\n")
        state.mark(name, status)
        state.save()

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = [ex.submit(job, m) for m in todo]
        for i, fut in enumerate(concurrent.futures.as_completed(futures), 1):
            fut.result()
            if i % 50 == 0 or i == len(futures):
                print(f"finished {i}/{len(futures)}")
    failures = state.failures()
    print(f"crawl complete; failures={len(failures)}")
    for name in failures:
        print(f"  failed: {name}")


if __name__ == "__main__":
    main()
