import io
import os
import zipfile

import pytest

from crawl.crawl import staged_extract


def _zip_bytes(entries=None):
    entries = entries or {"moon.mod": 'name = "a/b"\nversion = "0.1.0"\n'}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, content in entries.items():
            z.writestr(name, content)
    return buf.getvalue()


def _dest(tmp_path):
    return os.path.join(tmp_path, "corpus", "a", "b")


def test_staged_extract_cleans_stale_staging_leftover(tmp_path):
    dest = _dest(tmp_path)
    staging = f"{dest}.staging-{os.getpid()}"
    os.makedirs(staging)
    with open(os.path.join(staging, "partial"), "w") as f:
        f.write("truncated junk from a crashed run")
    staged_extract(_zip_bytes(), dest)
    assert not os.path.exists(staging)
    assert os.path.exists(os.path.join(dest, "moon.mod"))


def test_staged_extract_cleans_staging_on_failure(tmp_path):
    dest = _dest(tmp_path)
    staging = f"{dest}.staging-{os.getpid()}"
    with pytest.raises(zipfile.BadZipFile):
        staged_extract(b"definitely not a zip", dest)
    assert not os.path.exists(staging)
    assert not os.path.exists(dest)


def test_staged_extract_keeps_completed_destination(tmp_path):
    dest = _dest(tmp_path)
    os.makedirs(dest)
    with open(os.path.join(dest, "moon.mod"), "w") as f:
        f.write('name = "original/pkg"\n')
    staged_extract(_zip_bytes({"evil.mbt": "let x = 1\n"}), dest)
    # destination untouched; staging extracted then discarded
    assert sorted(os.listdir(dest)) == ["moon.mod"]
    with open(os.path.join(dest, "moon.mod")) as f:
        assert f.read() == 'name = "original/pkg"\n'
    assert not os.path.exists(f"{dest}.staging-{os.getpid()}")


def test_staged_extract_produces_scannable_tree(tmp_path):
    dest = _dest(tmp_path)
    staged_extract(
        _zip_bytes(
            {
                "pkg/moon.mod": 'name = "a/b"\n',
                "pkg/src/lib.mbt": "pub fn id(x : Int) -> Int { x }\n",
            }
        ),
        dest,
    )
    assert os.path.exists(os.path.join(dest, "pkg", "moon.mod"))
    assert os.path.exists(os.path.join(dest, "pkg", "src", "lib.mbt"))
