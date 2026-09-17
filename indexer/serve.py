# indexer/serve.py
"""Local web UI over the semantic package index, stdlib http.server only.

make_handler(index_dir, results_path, embedder) builds a request handler
whose GET / serves the PAGE_HTML single-page UI and GET /api/search answers
with exactly the CLI --json payload ([hit.__dict__], ensure_ascii=False) so
both surfaces stay isomorphic. serve() is blocking; pass open_browser=True
to open the default browser once the socket is bound.
"""
import argparse
import json
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from indexer.search import search

DEFAULT_PORT = 8765

PAGE_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>MoonBit package index — semantic search</title>
<style>
  body { font-family: system-ui, sans-serif; max-width: 720px; margin: 2rem auto; padding: 0 1rem; color: #1c2430; }
  h1 { font-size: 1.3rem; }
  form { display: flex; gap: .5rem; margin-bottom: 1.5rem; }
  #q { flex: 1; padding: .5rem .75rem; font-size: 1rem; border: 1px solid #b9c2cc; border-radius: 6px; }
  select, button { padding: .5rem .75rem; border: 1px solid #b9c2cc; border-radius: 6px; background: #fff; }
  button { cursor: pointer; }
  .card { border: 1px solid #dde3ea; border-radius: 8px; padding: .75rem 1rem; margin-bottom: .75rem; }
  .card header { display: flex; align-items: baseline; gap: .6rem; flex-wrap: wrap; }
  .name { font-weight: 600; }
  .version { color: #67727e; font-size: .85rem; }
  .score { margin-left: auto; font-variant-numeric: tabular-nums; color: #41505f; }
  .badge { font-size: .75rem; padding: .1rem .5rem; border-radius: 999px; border: 1px solid; }
  .badge.clean { color: #136c3a; border-color: #136c3a; background: #e7f6ed; }
  .badge.malicious { color: #a1172d; border-color: #a1172d; background: #fcebef; }
  .badge.suspicious { color: #8a5a00; border-color: #8a5a00; background: #fdf3dd; }
  .badge.unknown { color: #67727e; border-color: #b9c2cc; }
  .desc { margin: .4rem 0 0; color: #41505f; }
  #status { color: #a1172d; }
  .empty { color: #67727e; }
</style>
</head>
<body>
<h1>MoonBit package index — semantic search</h1>
<form id="f">
  <input id="q" name="q" placeholder="e.g. json path query" required autocomplete="off">
  <select id="verdict" aria-label="verdict filter">
    <option value="">any verdict</option>
    <option value="clean">clean</option>
    <option value="suspicious">suspicious</option>
    <option value="malicious">malicious</option>
  </select>
  <button>Search</button>
</form>
<p id="status" role="alert"></p>
<div id="results"></div>
<script>
const form = document.getElementById('f');
const status = document.getElementById('status');
const results = document.getElementById('results');

function badge(verdict) {
  const span = document.createElement('span');
  const cls = verdict ? verdict.toLowerCase() : 'unknown';
  span.className = 'badge ' + cls;
  span.textContent = verdict || 'unaudited';
  return span;
}

function card(hit) {
  const div = document.createElement('div');
  div.className = 'card';
  const header = document.createElement('header');
  const name = document.createElement('span');
  name.className = 'name';
  name.textContent = hit.module;
  const version = document.createElement('span');
  version.className = 'version';
  version.textContent = hit.version;
  header.append(name, version, badge(hit.verdict));
  const score = document.createElement('span');
  score.className = 'score';
  score.textContent = Number(hit.score).toFixed(4);
  header.append(score);
  const desc = document.createElement('p');
  desc.className = 'desc';
  desc.textContent = hit.description;
  div.append(header, desc);
  return div;
}

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  status.textContent = '';
  results.replaceChildren();
  const q = document.getElementById('q').value.trim();
  const verdict = document.getElementById('verdict').value;
  const params = new URLSearchParams({ q });
  if (verdict) params.set('verdict', verdict);
  let hits;
  try {
    const res = await fetch('/api/search?' + params);
    if (!res.ok) throw new Error('HTTP ' + res.status);
    hits = await res.json();
  } catch (err) {
    status.textContent = 'search failed: ' + err.message;
    return;
  }
  if (!hits.length) {
    const p = document.createElement('p');
    p.className = 'empty';
    p.textContent = 'No results.';
    results.append(p);
    return;
  }
  for (const hit of hits) results.append(card(hit));
});
</script>
</body>
</html>
"""


def make_handler(index_dir: Path, results_path: Path, embedder) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):  # stdlib signature, shadows builtin
            pass  # keep test/CLI output pristine

        def do_GET(self):
            url = urlparse(self.path)
            if url.path == "/":
                self._send(200, "text/html; charset=utf-8", PAGE_HTML.encode("utf-8"))
            elif url.path == "/api/search":
                self._api_search(parse_qs(url.query))
            else:
                self.send_error(404)

        def _api_search(self, params):
            q = params.get("q", [""])[0]
            if not q.strip():
                self.send_error(400, "missing required parameter: q")
                return
            try:
                n = int(params.get("n", ["10"])[0])
            except ValueError:
                self.send_error(400, "n must be an integer")
                return
            verdict = params.get("verdict", [None])[0] or None
            try:
                hits = search(q, n=n, verdict=verdict, index_dir=index_dir,
                              results_path=results_path, embedder=embedder)
            except ValueError as exc:
                self.send_error(400, str(exc))
                return
            body = json.dumps([h.__dict__ for h in hits],
                              ensure_ascii=False).encode("utf-8")
            self._send(200, "application/json; charset=utf-8", body)

        def _send(self, code, content_type, body):
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return Handler


def serve(port: int = DEFAULT_PORT, *, index_dir: Path = Path("index"),
          results_path: Path = Path("results/results.jsonl"), embedder=None,
          open_browser: bool = False) -> None:
    """Serve the UI on 127.0.0.1:port (blocking)."""
    if embedder is None:
        from indexer.api import GlmEmbedder
        embedder = GlmEmbedder()
    srv = HTTPServer(("127.0.0.1", port), make_handler(index_dir, results_path, embedder))
    url = f"http://127.0.0.1:{srv.server_address[1]}/"
    if open_browser:
        webbrowser.open(url)
    print(f"serving {url} (Ctrl-C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="python3 -m indexer.serve",
        description="Local web UI for the MoonBit semantic package index")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT,
                    help=f"port to listen on (default {DEFAULT_PORT})")
    ap.add_argument("--open", action="store_true",
                    help="open the UI in the default browser")
    args = ap.parse_args(argv)
    serve(port=args.port, open_browser=args.open)


if __name__ == "__main__":
    main()
