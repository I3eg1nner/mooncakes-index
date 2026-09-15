import io
import zipfile

from crawl.hotlist import pick_hot
from crawl.registry import parse_statistics_csv


def _stats_zip(rows: bytes) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("summary.txt", "total_lines 1\n")
        z.writestr("statistics.csv", rows)
    return buf.getvalue()


def test_pick_hot_prefers_downloads():
    stats = [("pop/x", 999), ("tiny/y", 1)]
    index = [{"name": "tiny/y"}, {"name": "pop/x"}, {"name": "mid/z"}]
    assert pick_hot(stats, index, top_n=2) == ["pop/x", "mid/z"]


def test_pick_hot_no_stats():
    index = [{"name": "a/b"}, {"name": "c/d"}]
    assert pick_hot([], index, top_n=1) == ["a/b"]


def test_parse_statistics_csv_real_layout():
    csv = (
        b"pkg_name,name,version,line_count,package_count,created_at\n"
        b"camel,ill/camel,0.1.0,25,2,2025-05-14T14:00:16\n"
        b"2048,sennenki/2048,0.1.1,1352,1,2026-09-10T02:25:25\n"
        b"bad,row-with-few-columns\n"
    )
    assert parse_statistics_csv(_stats_zip(csv)) == [("ill/camel", 25), ("sennenki/2048", 1352)]
