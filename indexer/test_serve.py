# indexer/test_serve.py
import json
import threading
import urllib.error
import urllib.request
from http.server import HTTPServer

from indexer import search as search_mod
from indexer.serve import make_handler
from indexer.testing import FakeEmbedder, build_index, write_results  # Task 3/4 提取的公共 helper


def test_api_search_same_shape_as_cli(tmp_path):
    index_dir = build_index(tmp_path)
    results_path = write_results(tmp_path)
    srv = HTTPServer(("127.0.0.1", 0),
                     make_handler(index_dir, results_path, FakeEmbedder()))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"

    # /api/search 与 CLI --json 同构
    want = [h.__dict__ for h in search_mod.search(
        "jmes", n=5, verdict=None, index_dir=index_dir,
        results_path=results_path, embedder=FakeEmbedder())]
    got = json.load(urllib.request.urlopen(f"{base}/api/search?q=jmes&n=5"))
    assert got == want

    # / 返回 HTML 页；缺 q 返回 400
    with urllib.request.urlopen(f"{base}/") as r:
        assert r.headers["Content-Type"].startswith("text/html")
    try:
        urllib.request.urlopen(f"{base}/api/search")
        assert False, "expected 400"
    except urllib.error.HTTPError as e:
        assert e.code == 400
    srv.shutdown()
