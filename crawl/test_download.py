import io
import zipfile

import pytest

from crawl.download import safe_extract


def make_zip(names):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for n in names:
            z.writestr(n, "x")
    return buf.getvalue()


def test_extract_ok(tmp_path):
    safe_extract(make_zip(["a/moon.mod", "a/src/x.mbt"]), str(tmp_path))
    assert (tmp_path / "a" / "moon.mod").exists()


def test_zip_slip_rejected(tmp_path):
    with pytest.raises(ValueError):
        safe_extract(make_zip(["../evil.txt"]), str(tmp_path))


def test_abs_path_rejected(tmp_path):
    with pytest.raises(ValueError):
        safe_extract(make_zip(["/etc/passwd"]), str(tmp_path))


def test_backslash_traversal_rejected(tmp_path):
    with pytest.raises(ValueError):
        safe_extract(make_zip(["..\\evil.txt"]), str(tmp_path))


def test_drive_letter_rejected(tmp_path):
    with pytest.raises(ValueError):
        safe_extract(make_zip(["C:\\evil.txt"]), str(tmp_path))


def test_too_many_files(tmp_path):
    with pytest.raises(ValueError):
        safe_extract(make_zip([f"f{i}.txt" for i in range(10)]), str(tmp_path), max_files=5)


def test_uncompressed_size_cap(tmp_path):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("big.bin", "x" * 1000)
    with pytest.raises(ValueError):
        safe_extract(buf.getvalue(), str(tmp_path), max_bytes=100)


def test_no_files_written_when_unsafe(tmp_path):
    with pytest.raises(ValueError):
        safe_extract(make_zip(["good.txt", "../evil.txt"]), str(tmp_path))
    assert not (tmp_path / "good.txt").exists()
