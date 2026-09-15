import io
import json
import threading
import time
import urllib.request
import zipfile

BASE = "https://mooncakes.io"
DL = "https://download.mooncakes.io"
UA = {"User-Agent": "mooncake-audit/0.1 (supply-chain research)"}
_last_get = 0.0
_lock = threading.Lock()


def _throttle(rate_limit: float, now_fn=time.monotonic, sleep_fn=time.sleep) -> None:
    global _last_get
    with _lock:
        wait = rate_limit - (now_fn() - _last_get)
        if wait > 0:
            sleep_fn(wait)
        _last_get = now_fn()


def fetch_bytes(url: str, rate_limit: float = 0.5) -> bytes:
    _throttle(rate_limit)
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def fetch_module_index() -> list[dict]:
    return json.loads(fetch_bytes(f"{BASE}/api/v0/modules").decode())


def download_url(name: str, version: str) -> str:
    return f"{DL}/user/{name}/{version}.zip"


def build_hotlist(path: str, modules: list[dict] | None = None, top_n: int = 100) -> list[str]:
    mods = modules if modules is not None else fetch_module_index()
    names = [m["name"] for m in mods[:top_n]]
    with open(path, "w") as f:
        f.write("\n".join(names))
    return names


def parse_statistics_csv(data: bytes) -> list[tuple[str, int]]:
    z = zipfile.ZipFile(io.BytesIO(data))
    rows = []
    for line in z.read(z.namelist()[0]).decode().splitlines()[1:]:
        parts = line.split(",")
        if len(parts) >= 2:
            try:
                rows.append((parts[0], int(parts[1])))
            except ValueError:
                pass
    return rows
