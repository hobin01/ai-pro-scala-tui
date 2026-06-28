from collections.abc import Callable, Coroutine
from typing import Any

import anyio
import pytest
from anyio.abc import TaskGroup

from scala_backend.app_factory import create_app
from scala_backend.config import BackendConfig
from scala_backend.models import JsonObject


class InlinePeer:
    def __init__(self, task_group: TaskGroup) -> None:
        self.task_group = task_group
        self.messages: list[tuple[str, JsonObject]] = []
        self.running = anyio.Event()

    async def notify(self, method: str, params: JsonObject) -> None:
        self.messages.append((method, params))
        if method == "run.status" and params.get("status") == "running":
            self.running.set()

    async def request(self, method: str, params: JsonObject) -> JsonObject:
        self.messages.append((method, params))
        return {"decision": "approve"}

    def start_soon(
        self,
        func: Callable[..., Coroutine[Any, Any, None]],
        *args: object,
    ) -> None:
        self.task_group.start_soon(func, *args)


@pytest.mark.anyio
async def test_pipeline_surface_returns_run_id() -> None:
    app = create_app(BackendConfig())
    async with anyio.create_task_group() as task_group:
        peer = InlinePeer(task_group)
        result = await app.handle(
            "pipeline.run",
            {"sources": [{"solution": "splunk", "index": "main"}]},
            peer,
        )
        with anyio.fail_after(1):
            await peer.running.wait()
        assert "run_id" in result
        assert (
            "run.status",
            {"run_id": result["run_id"], "status": "running"},
        ) in peer.messages
        task_group.cancel_scope.cancel()
