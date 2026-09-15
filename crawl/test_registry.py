import threading
import time

import pytest

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


class _FakeResponse:
    def read(self):
        return b"ok"

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_fetch_bytes_retries_then_succeeds(monkeypatch):
    monkeypatch.setattr(reg, "_throttle", lambda rate_limit: None)
    attempts = []

    def fake_urlopen(req, timeout):
        attempts.append(1)
        if len(attempts) < 3:
            raise reg.urllib.error.URLError("transient")
        return _FakeResponse()

    sleeps = []
    monkeypatch.setattr(reg.time, "sleep", sleeps.append)
    monkeypatch.setattr(reg.urllib.request, "urlopen", fake_urlopen)
    assert reg.fetch_bytes("http://example/") == b"ok"
    assert len(attempts) == 3
    assert sleeps == [0.5, 1.0]


def test_fetch_bytes_persistent_failure_raises(monkeypatch):
    monkeypatch.setattr(reg, "_throttle", lambda rate_limit: None)
    attempts = []

    def fake_urlopen(req, timeout):
        attempts.append(1)
        raise reg.urllib.error.URLError("down")

    monkeypatch.setattr(reg.time, "sleep", lambda s: None)
    monkeypatch.setattr(reg.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(reg.urllib.error.URLError):
        reg.fetch_bytes("http://example/")
    assert len(attempts) == 1 + len(reg.RETRY_DELAYS)


def test_fetch_bytes_retries_http_5xx_but_not_404(monkeypatch):
    monkeypatch.setattr(reg, "_throttle", lambda rate_limit: None)
    monkeypatch.setattr(reg.time, "sleep", lambda s: None)

    calls = []

    def five_oh_three(req, timeout):
        calls.append(1)
        raise reg.urllib.error.HTTPError(req.full_url, 503, "Service Unavailable", None, None)

    monkeypatch.setattr(reg.urllib.request, "urlopen", five_oh_three)
    with pytest.raises(reg.urllib.error.HTTPError):
        reg.fetch_bytes("http://example/")
    assert len(calls) == 1 + len(reg.RETRY_DELAYS)

    def not_found(req, timeout):
        calls.append(1)
        raise reg.urllib.error.HTTPError(req.full_url, 404, "Not Found", None, None)

    monkeypatch.setattr(reg.urllib.request, "urlopen", not_found)
    calls.clear()
    with pytest.raises(reg.urllib.error.HTTPError):
        reg.fetch_bytes("http://example/")
    assert len(calls) == 1, "404 must not be retried"


def test_download_url_quotes_special_chars():
    # '+' in build-metadata versions must be %2B (raw '+' 404s on the CDN)
    assert (
        reg.download_url("bzy-debug/hello", "0.1.20240510+81e045f4e")
        == "https://download.mooncakes.io/user/bzy-debug/hello/0.1.20240510%2B81e045f4e.zip"
    )
    # non-ascii module names must be percent-encoded, '/' preserved
    assert reg.download_url("CAIMEOX/原来可以发中文包", "0.1.0").startswith(
        "https://download.mooncakes.io/user/CAIMEOX/%E5%8E%9F"
    )
    # plain names unchanged
    assert (
        reg.download_url("a/b", "1.0.0")
        == "https://download.mooncakes.io/user/a/b/1.0.0.zip"
    )
