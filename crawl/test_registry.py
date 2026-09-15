import threading
import time

from crawl import registry as reg
from crawl.registry import build_hotlist, download_url


def test_download_url():
    assert download_url("daqing/moonkafka", "0.2.1") == "https://download.mooncakes.io/user/daqing/moonkafka/0.2.1.zip"


def test_hotlist(tmp_path):
    p = tmp_path / "hot.txt"
    mods = [{"name": "a/b", "version": "1.0"}, {"name": "c/d", "version": "2.0"}]
    hot = build_hotlist(str(p), modules=mods, top_n=1)
    assert hot == ["a/b"]
    assert p.read_text().strip() == "a/b"


def test_throttle_serializes_concurrent_calls():
    n = 8
    barrier = threading.Barrier(n)
    lock_held_during_sleep = []
    in_sleep = 0
    overlapped = [False]

    def now_fn():
        return 100.0

    def sleep_fn(seconds):
        nonlocal in_sleep
        lock_held_during_sleep.append(reg._lock.locked())
        in_sleep += 1
        if in_sleep > 1:
            overlapped[0] = True
        time.sleep(0.005)
        in_sleep -= 1

    def worker():
        barrier.wait()
        reg._throttle(0.5, now_fn=now_fn, sleep_fn=sleep_fn)

    reg._last_get = 100.0
    threads = [threading.Thread(target=worker) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(lock_held_during_sleep) == n
    assert all(lock_held_during_sleep), "wait/sleep must happen while holding _lock"
    assert not overlapped[0], "concurrent throttle calls overlapped"
    assert reg._last_get == 100.0


def test_fetch_bytes_throttles(monkeypatch):
    calls = []
    monkeypatch.setattr(reg, "_throttle", lambda rate_limit: calls.append(rate_limit))

    class FakeResponse:
        def read(self):
            return b"ok"

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(reg.urllib.request, "urlopen", lambda req, timeout: FakeResponse())
    assert reg.fetch_bytes("http://example/", rate_limit=0.25) == b"ok"
    assert calls == [0.25]
