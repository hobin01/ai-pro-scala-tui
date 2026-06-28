from __future__ import annotations

import anyio
from anyio.abc import SocketStream

from scala_backend.app import BackendApp
from scala_backend.config import BackendConfig
from scala_backend.jsonrpc import JsonRpcConnection, JsonRpcPeer, RpcHandler
from scala_backend.models import JsonObject


async def serve(config: BackendConfig, app: BackendApp) -> None:
    listener = await anyio.create_tcp_listener(
        local_host=config.backend_host,
        local_port=config.backend_port,
    )
    connection = JsonRpcConnection(_make_handler(app))
    await listener.serve(connection.run)


def _make_handler(app: BackendApp) -> RpcHandler:
    async def handle(method: str, params: JsonObject, peer: JsonRpcPeer) -> JsonObject:
        return await app.handle(method, params, peer)

    return handle


async def probe_once(stream: SocketStream, payload: bytes) -> bytes:
    await stream.send(payload)
    return await stream.receive()
