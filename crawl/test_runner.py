import stat
import textwrap

from crawl.runner import scan_package


def _write_engine(tmp_path, body):
    p = tmp_path / "fake_engine.sh"
    p.write_text(textwrap.dedent(body))
    p.chmod(p.stat().st_mode | stat.S_IEXEC)
    return str(p)


def test_scan_package_parses_json(tmp_path):
    engine = _write_engine(
        tmp_path,
        '#!/bin/sh\necho \'{"module":"a/b","risk":30,"verdict":"Suspicious","findings":[],"errors":[]}\'\n',
    )
    r = scan_package(engine, "/tmp/fakepkg", None)
    assert r["verdict"] == "Suspicious"


def test_scan_package_timeout(tmp_path):
    engine = _write_engine(tmp_path, "#!/bin/sh\nsleep 10\n")
    r = scan_package(engine, "/tmp/fakepkg", None, timeout=1)
    assert "error" in r


def test_scan_package_missing_binary(tmp_path):
    r = scan_package(str(tmp_path / "no_such_engine"), "/tmp/fakepkg", None, timeout=5)
    assert "error" in r
    assert r["module"] == "/tmp/fakepkg"
