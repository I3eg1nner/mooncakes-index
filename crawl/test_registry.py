from crawl.registry import build_hotlist, download_url


def test_download_url():
    assert download_url("daqing/moonkafka", "0.2.1") == "https://download.mooncakes.io/user/daqing/moonkafka/0.2.1.zip"


def test_hotlist(tmp_path):
    p = tmp_path / "hot.txt"
    mods = [{"name": "a/b", "version": "1.0"}, {"name": "c/d", "version": "2.0"}]
    hot = build_hotlist(str(p), modules=mods, top_n=1)
    assert hot == ["a/b"]
    assert p.read_text().strip() == "a/b"
