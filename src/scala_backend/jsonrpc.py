from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, Coroutine
from dataclasses import dataclass
from itertools import count
from typing import Any

import anyio
from anyio import EndOfStream, IncompleteRead
from anyio.abc import SocketStream, TaskGroup
from anyio.streams.buffered import BufferedByteReceiveStream
from pydantic import ValidationError

from scala_backend.errors import (
    JSON_RPC_INVALID_REQUEST,
    JSON_RPC_PARSE_ERROR,
    InvalidParamsError,
    MethodNotFoundError,
    payload_from_exception,
)
from scala_backend.models import JsonId, JsonObject, JsonValue

RpcHandler = Callable[[str, JsonObject, "JsonRpcPeer"], Awaitable[JsonObject]]


@dataclass
class _PendingResponse:
    event: anyio.Event
    payload: JsonObject | None = None


class JsonRpcPeer:
    def __init__(self, stream: SocketStream, task_group: TaskGroup) -> None:
        self._stream = stream
        self._task_group = task_group
        self._send_lock = anyio.Lock()
        self._next_id = count(1)
        self._pending: dict[JsonId, _PendingResponse] = {}

    async def notify(self, method: str, params: JsonObject) -> None:
        await self.send({"jsonrpc": "2.0", "method": method, "params": params})

    async def request(self, method: str, params: JsonObject) -> JsonObject:
        request_id = f"srv-{next(self._next_id)}"
        pending = _PendingResponse(event=anyio.Event())
        self._pending[request_id] = pending
        await self.send(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": method,
                "params": params,
            },
        )
        await pending.event.wait()
        response = pending.payload or {}
        if "error" in response:
            raise InvalidParamsError(str(response["error"]))
        result = response.get("result", {})
        if not isinstance(result, dict):
            raise InvalidParamsError("response result must be an object")
        return result

    def start_soon(
        self,
        func: Callable[..., Coroutine[Any, Any, None]],
        *args: object,
    ) -> None:
        self._task_group.start_soon(func, *args)

    async def send(self, message: JsonObject) -> None:
        payload = json.dumps(message, ensure_ascii=False, separators=(",", ":"))
        async with self._send_lock:
            await self._stream.send((payload + "\n").encode("utf-8"))

    def accept_response(self, message: JsonObject) -> bool:
        request_id = _json_id(message.get("id"))
        pending = self._pending.pop(request_id, None)
        if pending is None:
            return False
        pending.payload = message
        pending.event.set()
        return True


class JsonRpcConnection:
    def __init__(self, handler: RpcHandler) -> None:
        self._handler = handler

    async def run(self, stream: SocketStream) -> None:
        async with anyio.create_task_group() as task_group:
            peer = JsonRpcPeer(stream, task_group)
            buffered = BufferedByteReceiveStream(stream)
            while True:
                try:
                    line = await buffered.receive_until(b"\n", 1_048_576)
                except (EndOfStream, IncompleteRead):
                    break
                await self._handle_line(peer, line)

    async def _handle_line(self, peer: JsonRpcPeer, line: bytes) -> None:
        message, error = decode_message_line(line)
        if error is not None:
            await peer.send(error)
            return
        if message is None:
            return
        if "method" not in message:
            peer.accept_response(message)
            return
        request_id = _json_id(message.get("id"))
        try:
            result = await self._dispatch(peer, message)
        except (InvalidParamsError, MethodNotFoundError, ValidationError) as exc:
            if request_id is not None:
                payload = payload_from_exception(exc)
                await peer.send(
                    _error(request_id, payload.code, payload.message, payload.data)
                )
            return
        except Exception as exc:
            if request_id is not None:
                payload = payload_from_exception(exc)
                await peer.send(
                    _error(request_id, payload.code, payload.message, payload.data)
                )
            return
        if request_id is not None:
            await peer.send({"jsonrpc": "2.0", "id": request_id, "result": result})

    async def _dispatch(self, peer: JsonRpcPeer, message: JsonObject) -> JsonObject:
        if message.get("jsonrpc") != "2.0":
            raise InvalidParamsError("jsonrpc must be 2.0")
        method = message.get("method")
        if not isinstance(method, str):
            raise InvalidParamsError("method must be a string")
        params = message.get("params", {})
        if not isinstance(params, dict):
            raise InvalidParamsError("params must be an object")
        return await self._handler(method, params, peer)


def _error(
    request_id: JsonId,
    code: int,
    message: str,
    data: dict[str, str] | None = None,
) -> JsonObject:
    payload: dict[str, JsonValue] = {"code": code, "message": message}
    if data is not None:
        payload["data"] = data
    return {"jsonrpc": "2.0", "id": request_id, "error": payload}


def decode_message_line(line: bytes) -> tuple[JsonObject | None, JsonObject | None]:
    try:
        raw = json.loads(line.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None, _error(None, JSON_RPC_PARSE_ERROR, "parse_error")
    if not isinstance(raw, dict):
        return None, _error(None, JSON_RPC_INVALID_REQUEST, "invalid_request")
    return raw, None


def _json_id(value: JsonValue) -> JsonId:
    return value if isinstance(value, str | int) or value is None else None
