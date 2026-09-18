# indexer/test_mcp_server.py
import asyncio
import json
import threading

import pytest

from indexer import mcp_server
from indexer.testing import FakeEmbedder, build_index, write_results


@pytest.fixture()
def mcp_env(tmp_path, monkeypatch):
    monkeypatch.setenv("INDEXER_INDEX_DIR", str(tmp_path / "index"))
    monkeypatch.setenv("INDEXER_RESULTS_PATH", str(tmp_path / "results.jsonl"))
    monkeypatch.setenv("INDEXER_REGISTRY_PATH", str(tmp_path / "registry.json"))
    build_index(tmp_path)  # 复用现有 helper：chunks.db + vectors.npy + registry 桩
    write_results(tmp_path)
    return tmp_path


def make_server():
    return mcp_server.create_mcp(embedder=FakeEmbedder())


def run(coro):
    return asyncio.run(coro)


def _first_module(index_dir):
    import sqlite3
    return sqlite3.connect(index_dir / "chunks.db").execute(
        "SELECT module FROM chunks ORDER BY id LIMIT 1").fetchone()[0]


def test_tools_registered(mcp_env):
    from mcp.shared.memory import create_connected_server_and_client_session

    async def go():
        async with create_connected_server_and_client_session(make_server()) as s:
            await s.initialize()
            tools = await s.list_tools()
            return {t.name for t in tools.tools}

    assert run(go()) == {"search_modules", "get_module"}


def test_search_modules_roundtrip(mcp_env):
    from mcp.shared.memory import create_connected_server_and_client_session

    async def go():
        async with create_connected_server_and_client_session(make_server()) as s:
            await s.initialize()
            return await s.call_tool("search_modules", {"query": "jmes", "n": 5})

    res = run(go())
    assert res.isError is False
    hits = json.loads(res.content[0].text)
    assert isinstance(hits, list) and hits and {"module", "version", "score"} <= set(hits[0])


def test_get_module_payload_and_error(mcp_env):
    from mcp.shared.memory import create_connected_server_and_client_session
    name = _first_module(mcp_env / "index")

    async def go(nm):
        async with create_connected_server_and_client_session(make_server()) as s:
            await s.initialize()
            return await s.call_tool("get_module", {"name": nm})

    d = json.loads(run(go(name)).content[0].text)
    assert d.get("name") == name and "api_surface" in d and "findings" in d
    miss = json.loads(run(go("no/such-module-xyz")).content[0].text)
    assert miss["error"] == "module_not_found" and len(miss["suggestions"]) <= 3


def test_search_invalid_argument(mcp_env):
    from mcp.shared.memory import create_connected_server_and_client_session

    async def go():
        async with create_connected_server_and_client_session(make_server()) as s:
            await s.initialize()
            return await s.call_tool("search_modules", {"query": "", "n": 5})

    assert json.loads(run(go()).content[0].text)["error"] == "invalid_argument"


def test_search_missing_api_key(mcp_env, monkeypatch):
    from mcp.shared.memory import create_connected_server_and_client_session

    monkeypatch.delenv("ZHIPUAI_API_KEY", raising=False)
    monkeypatch.delenv("API_KEY", raising=False)

    async def go():
        async with create_connected_server_and_client_session(mcp_server.create_mcp()) as s:
            await s.initialize()
            return await s.call_tool("search_modules", {"query": "jmes", "n": 5})

    payload = json.loads(run(go()).content[0].text)
    assert payload["error"] == "missing_api_key"
    assert "ZHIPUAI_API_KEY" in payload["hint"]


def test_search_embedder_unavailable(mcp_env):
    from mcp.shared.memory import create_connected_server_and_client_session

    class BoomEmbedder:
        def embed(self, texts):
            raise RuntimeError("boom")

    async def go():
        async with create_connected_server_and_client_session(
                mcp_server.create_mcp(embedder=BoomEmbedder())) as s:
            await s.initialize()
            return await s.call_tool("search_modules", {"query": "jmes", "n": 5})

    payload = json.loads(run(go()).content[0].text)
    assert payload["error"] == "embedder_unavailable" and "boom" in payload["detail"]


def test_search_index_not_built(mcp_env, monkeypatch):
    from mcp.shared.memory import create_connected_server_and_client_session

    monkeypatch.setenv("INDEXER_INDEX_DIR", str(mcp_env / "no-such-index"))

    async def go():
        async with create_connected_server_and_client_session(
                mcp_server.create_mcp(embedder=FakeEmbedder())) as s:
            await s.initialize()
            return await s.call_tool("search_modules", {"query": "jmes", "n": 5})

    payload = json.loads(run(go()).content[0].text)
    assert payload["error"] == "index_not_built" and "hint" in payload


def test_search_verdict_filter_via_mcp(mcp_env):
    """write_results 桩已含 evil/pwn=Malicious、bobzhang/moonjq=Clean。"""
    from mcp.shared.memory import create_connected_server_and_client_session

    async def go():
        async with create_connected_server_and_client_session(make_server()) as s:
            await s.initialize()
            return await s.call_tool(
                "search_modules", {"query": "jmes", "n": 5, "verdict": "clean"})

    hits = json.loads(run(go()).content[0].text)
    assert hits and all(h["verdict"] == "Clean" for h in hits)
    assert all(h["module"] != "evil/pwn" for h in hits)


def test_http_transport_roundtrip(mcp_env):
    """spec §7/§8.3：streamable-http 起 127.0.0.1:0 服务后 list/call 一轮。"""
    from mcp.client.session import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    mcp = make_server()
    app = mcp.streamable_http_app()
    import uvicorn
    config = uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning")
    server = uvicorn.Server(config)
    th = threading.Thread(target=server.run, daemon=True)
    th.start()
    while not server.started:
        threading.Event().wait(0.05)
    port = server.servers[0].sockets[0].getsockname()[1]

    async def go():
        async with streamablehttp_client(f"http://127.0.0.1:{port}/mcp") as (r, w, _):
            async with ClientSession(r, w) as s:
                await s.initialize()
                tools = await s.list_tools()
                res = await s.call_tool("get_module", {"name": _first_module(mcp_env / "index")})
                return {t.name for t in tools.tools}, json.loads(res.content[0].text)

    names, payload = run(go())
    assert names == {"search_modules", "get_module"}
    assert payload.get("name") == _first_module(mcp_env / "index")
    server.should_exit = True
    th.join(timeout=5)
