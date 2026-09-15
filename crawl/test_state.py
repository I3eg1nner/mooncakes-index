from crawl.state import CrawlState


def test_state_roundtrip(tmp_path):
    p = tmp_path / "s.json"
    s = CrawlState.load(str(p))
    s.mark("a/b", "ok")
    s.save()
    s2 = CrawlState.load(str(p))
    assert s2.done("a/b")
    assert not s2.done("c/d")


def test_state_failures(tmp_path):
    p = tmp_path / "s.json"
    s = CrawlState.load(str(p))
    s.mark("x/y", "fail:timeout")
    s.save()
    s2 = CrawlState.load(str(p))
    assert s2.failures() == ["x/y"]
