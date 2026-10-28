# mooncacke — mooncakes.io corpus, audit results & semantic index

Data-side companion to [mooncake-audit](../mooncake-audit) (the MoonBit detector engine, now a standalone repository). This repo keeps:

- **Crawl orchestrator** (`crawl/`) — downloads packages from mooncakes.io (rate-limited, zip-slip-safe), scans each with the detector engine binary, appends results
- **Audit results** (`results/`) — per-module JSONL reports and grouped summaries
- **Semantic index** (`indexer/`) — chunks package metadata/README/.mbti into SQLite, embeds with GLM `embedding-3` (1024 dims, content-addressed & incremental), natural-language search with audit verdicts joined, MCP server for LLM agents

## Engine

The scan engine now lives in its own repo (GitHub-ready: CI, canaries, rule catalog, SARIF output). Build it there first:

```bash
git clone <mooncake-audit repo> /tmp/mooncake-audit
cd /tmp/mooncake-audit && moon build --target native --release
ENGINE=$(find _build/native/release -type f -executable | head -1)
```

## Crawl the registry

```bash
python3 -m crawl.hotlist --out state/hotlist.txt --top 100
python3 -m crawl.crawl --engine "$ENGINE" --modules all
python3 -c "from crawl.report import write_summary; write_summary('results/results.jsonl','results/summary.md')"
```

Resumable via `state/crawl_state.json`; `--modules all|sample:N|file:LIST`.

## Semantic index

```bash
python3 -m indexer.collect
python3 -m indexer.embed          # incremental: only new/changed chunks
python3 -m indexer.search "jmes" -n 5
python3 -m indexer.serve --port 8765
```

Embedding needs `ZHIPUAI_API_KEY`/`API_KEY` (+ optional `Base_URL`/`Model`) in `.env`. Embeddings are content-addressed (chunk sha256) — re-running collect+embed after a corpus update costs only the new chunks.

## MCP server

```bash
pip install -r requirements.txt
python3 -m indexer.mcp_server            # stdio
python3 -m indexer.mcp_server --http --port 8000
```

Tools: `search_modules(query, n, verdict)`, `get_module(name)`.

## Development

- `python3 -m pytest crawl/ indexer/ -v`
- `state/`, `corpus/`, `results/`, `index/`, `.repos/` are gitignored.
