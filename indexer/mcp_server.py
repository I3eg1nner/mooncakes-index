# indexer/mcp_server.py
"""MCP server exposing the semantic package index to LLM agents.

Tools: search_modules(query, n, verdict), get_module(name).
Transports: stdio (default) or streamable-http (--http --port N).
All tool errors are structured JSON strings — never bare exceptions.
"""
import argparse
import json
import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from indexer.search import REGISTRY_DEFAULT


def _env_paths() -> tuple[Path, Path, Path]:
    return (Path(os.environ.get("INDEXER_INDEX_DIR", "index")),
            Path(os.environ.get("INDEXER_RESULTS_PATH", "results/results.jsonl")),
            Path(os.environ.get("INDEXER_REGISTRY_PATH", REGISTRY_DEFAULT)))


def create_mcp(index_dir: Path | None = None, results_path: Path | None = None,
               registry_path: Path | None = None, embedder=None) -> FastMCP:
    idx, res, reg = _env_paths()
    index_dir = index_dir or idx
    results_path = results_path or res
    registry_path = registry_path or reg

    mcp = FastMCP("mooncake-index")

    @mcp.tool()
    def search_modules(query: str, n: int = 10, verdict: str | None = None) -> str:
        """Semantic search over the mooncakes.io index. Returns a JSON list of
        {module, version, score, verdict, risk, description} candidates."""
        from indexer import api, search as search_mod
        try:
            if not (Path(index_dir) / "chunks.db").is_file():
                return json.dumps({"error": "index_not_built",
                                   "hint": "run: python3 -m indexer.collect && python3 -m indexer.embed"})
            emb = embedder or api.GlmEmbedder()
            hits = search_mod.search(query, n=n, verdict=verdict, index_dir=index_dir,
                                     results_path=results_path, embedder=emb,
                                     registry_path=registry_path)
            return json.dumps([h.__dict__ for h in hits], ensure_ascii=False)
        except ValueError as e:
            return json.dumps({"error": "invalid_argument", "detail": str(e)})
        except api.MissingKeyError:
            return json.dumps({"error": "missing_api_key",
                               "hint": "set ZHIPUAI_API_KEY or API_KEY"})
        except Exception as e:  # 网络类异常已在上游退避重试后仍失败
            return json.dumps({"error": "embedder_unavailable", "detail": repr(e)})

    @mcp.tool()
    def get_module(name: str) -> str:
        """Full judgment payload for one module: audit verdict/risk/findings,
        API surface, README summary. Local-only (no GLM needed)."""
        from indexer.detail import build_module_detail
        try:
            d = build_module_detail(name, index_dir=index_dir,
                                    results_path=results_path, registry_path=registry_path)
            return json.dumps(d, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": "detail_unavailable", "detail": repr(e)})

    return mcp


def main() -> None:
    ap = argparse.ArgumentParser(prog="indexer.mcp_server")
    ap.add_argument("--http", action="store_true", help="streamable-http transport")
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()
    mcp = create_mcp()
    if args.http:
        mcp.settings.port = args.port
        mcp.run(transport="streamable-http")
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
