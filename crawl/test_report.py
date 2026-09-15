import json

from crawl.report import write_summary


def _write_results(path, entries):
    lines = [e if isinstance(e, str) else json.dumps(e) for e in entries]
    path.write_text("\n".join(lines) + "\n")


def test_summary_skips_malformed_lines_and_dedups(tmp_path, capsys):
    results = tmp_path / "results.jsonl"
    _write_results(
        results,
        [
            {"module": "a/b", "version": "1", "verdict": "Clean", "risk": 0, "findings": []},
            "THIS IS NOT JSON",
            {
                "module": "a/b",
                "version": "2",
                "verdict": "Suspicious",
                "risk": 15,
                "findings": [{"rule": "S02"}],
            },
            {"module": "c/d", "version": "1", "verdict": "Clean", "risk": 0, "findings": []},
        ],
    )
    out = tmp_path / "summary.md"
    write_summary(str(results), str(out))
    text = out.read_text()
    # deduped to 2 modules (a/b last row wins -> Suspicious v2)
    assert "scanned: 2" in text
    assert "## Clean (1)" in text
    assert "## Suspicious (1)" in text
    assert "| a/b | 2 | 15 | S02 |" in text
    assert "skipped 1 malformed result line(s)" in capsys.readouterr().err


def test_summary_all_malformed_still_writes(tmp_path, capsys):
    results = tmp_path / "results.jsonl"
    _write_results(results, ["{broken", "}}}"])
    out = tmp_path / "summary.md"
    write_summary(str(results), str(out))
    assert "scanned: 0" in out.read_text()
    assert "skipped 2 malformed result line(s)" in capsys.readouterr().err
