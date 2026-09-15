import io
import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

BASE = "https://mooncakes.io"
DL = "https://download.mooncakes.io"
UA = {"User-Agent": "mooncake-audit/0.1 (supply-chain research)"}
_last_get = 0.0
_lock = threading.Lock()

# exponential backoff between fetch attempts (seconds); initial attempt plus
# up to len(RETRY_DELAYS) retries. 4xx responses raise immediately (no retry).
RETRY_DELAYS = (0.5, 1.0, 2.0)


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
    last_err: Exception | None = None
    for i in range(len(RETRY_DELAYS) + 1):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if not 500 <= e.code <= 599:
                raise
            last_err = e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last_err = e
        if i < len(RETRY_DELAYS):
            time.sleep(RETRY_DELAYS[i])  # backoff outside the rate-limit lock
    raise last_err


def fetch_module_index() -> list[dict]:
    return json.loads(fetch_bytes(f"{BASE}/api/v0/modules").decode())


def download_url(name: str, version: str) -> str:
    # quote is required: '+' in build-metadata versions must reach the server
    # percent-encoded (%2B), and non-ascii module names (CJK, emoji) cannot be
    # sent raw by urllib at all.
    path = urllib.parse.quote(f"{name}/{version}.zip", safe="/")
    return f"{DL}/user/{path}"


def build_hotlist(path: str, modules: list[dict] | None = None, top_n: int = 100) -> list[str]:
    mods = modules if modules is not None else fetch_module_index()
    names = [m["name"] for m in mods[:top_n]]
    with open(path, "w") as f:
        f.write("\n".join(names))
    return names


def parse_statistics_csv(data: bytes) -> list[tuple[str, int]]:
    z = zipfile.ZipFile(io.BytesIO(data))
    name = next((n for n in z.namelist() if n.endswith("statistics.csv")), z.namelist()[0])
    rows = []
    for line in z.read(name).decode().splitlines()[1:]:
        parts = line.split(",")
        if len(parts) >= 4:
            try:
                rows.append((parts[1], int(parts[3])))
            except ValueError:
                pass
    return rows
