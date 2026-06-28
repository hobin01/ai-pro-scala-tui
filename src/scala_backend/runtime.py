from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any, cast

from scala_backend.models import JsonObject


async def notify(peer: object, method: str, params: JsonObject) -> None:
    sender = getattr(peer, "notify", None)
    if sender is not None:
        await sender(method, params)


async def request(peer: object, method: str, params: JsonObject) -> JsonObject:
    sender = getattr(peer, "request", None)
    if sender is None:
        return {"decision": "approve"}
    return cast("JsonObject", await sender(method, params))


def start_soon(
    peer: object,
    func: Callable[..., Coroutine[Any, Any, None]],
    *args: object,
) -> None:
    starter = getattr(peer, "start_soon", None)
    if starter is not None:
        starter(func, *args)
