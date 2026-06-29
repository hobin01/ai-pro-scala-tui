from __future__ import annotations

import anyio
from anyio.abc import SocketStream

from scala_backend.app import BackendApp
from scala_backend.config import BackendConfig
from scala_backend.jsonrpc import JsonRpcConnection, JsonRpcPeer, RpcHandler
from scala_backend.models import JsonObject


async def serve(config: BackendConfig, app: BackendApp) -> None:
    """TCP listener를 열어 JSON-RPC backend app을 연결마다 붙인다."""
    listener = await anyio.create_tcp_listener(
        local_host=config.backend_host,
        local_port=config.backend_port,
    )
    connection = JsonRpcConnection(_make_handler(app))
    await listener.serve(connection.run)


def _make_handler(app: BackendApp) -> RpcHandler:
    """TCP JSON-RPC 서버의 make handler 보조 경로를 분리한다."""

    async def handle(method: str, params: JsonObject, peer: JsonRpcPeer) -> JsonObject:
        """한 TCP 연결의 JSON-RPC read/write loop를 BackendApp에 연결한다."""
        return await app.handle(method, params, peer)

    return handle


async def probe_once(stream: SocketStream, payload: bytes) -> bytes:
    """backend listen socket이 준비됐는지 짧은 TCP probe로 확인한다."""
    await stream.send(payload)
    return await stream.receive()
