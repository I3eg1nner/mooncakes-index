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


def test_scan_package_passes_module_and_version(tmp_path):
    engine = _write_engine(
        tmp_path,
        '#!/bin/sh\nprintf \'{"module":"x","args":"%s"}\\n\' "$*"\n',
    )
    r = scan_package(engine, "/tmp/fakepkg", None, module="evil/asynx", version="0.2.0")
    assert "--module evil/asynx" in r["args"]
    assert "--version 0.2.0" in r["args"]


def test_scan_package_omits_module_flags_when_absent(tmp_path):
    engine = _write_engine(
        tmp_path,
        '#!/bin/sh\nprintf \'{"module":"x","args":"%s"}\\n\' "$*"\n',
    )
    r = scan_package(engine, "/tmp/fakepkg", None)
    assert "--module" not in r["args"]
    assert "--version" not in r["args"]
