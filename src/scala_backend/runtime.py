from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any, cast

from scala_backend.models import JsonObject


async def notify(peer: object, method: str, params: JsonObject) -> None:
    """runtime peer에 progress notification을 보낸다."""
    sender = getattr(peer, "notify", None)
    if sender is not None:
        await sender(method, params)


async def request(peer: object, method: str, params: JsonObject) -> JsonObject:
    """runtime peer에 server-originated request를 보내 응답을 기다린다."""
    sender = getattr(peer, "request", None)
    if sender is None:
        return {"decision": "approve"}
    return cast("JsonObject", await sender(method, params))


def start_soon(
    peer: object,
    func: Callable[..., Coroutine[Any, Any, None]],
    *args: object,
) -> None:
    """runtime peer의 task group에 coroutine을 등록한다."""
    starter = getattr(peer, "start_soon", None)
    if starter is not None:
        starter(func, *args)
