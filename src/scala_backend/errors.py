from __future__ import annotations

from dataclasses import dataclass
from typing import Final

JSON_RPC_INTERNAL_ERROR: Final = -32603
JSON_RPC_INVALID_PARAMS: Final = -32602
JSON_RPC_METHOD_NOT_FOUND: Final = -32601
JSON_RPC_INVALID_REQUEST: Final = -32600
JSON_RPC_PARSE_ERROR: Final = -32700


@dataclass(frozen=True)
class JsonRpcErrorPayload:
    code: int
    message: str
    data: dict[str, str] | None = None


class ScalaBackendError(Exception):
    rpc_code = -32000
    public_message = "backend_error"

    def __init__(self, detail: str = "") -> None:
        super().__init__(detail)
        self.detail = detail

    def to_payload(self) -> JsonRpcErrorPayload:
        data = {"detail": self.detail} if self.detail else None
        return JsonRpcErrorPayload(
            code=self.rpc_code,
            message=self.public_message,
            data=data,
        )


class ConfigurationError(ScalaBackendError):
    rpc_code = -32010
    public_message = "settings_incomplete"


class InvalidParamsError(ScalaBackendError):
    rpc_code = JSON_RPC_INVALID_PARAMS
    public_message = "invalid_params"


class MethodNotFoundError(ScalaBackendError):
    rpc_code = JSON_RPC_METHOD_NOT_FOUND
    public_message = "method_not_found"


class ResourceNotFoundError(ScalaBackendError):
    rpc_code = -32002
    public_message = "not_found"


class RunInProgressError(ScalaBackendError):
    rpc_code = -32003
    public_message = "run_in_progress"


class SourceUnavailableError(ScalaBackendError):
    rpc_code = -32004
    public_message = "source_unreachable"


class ProviderError(ScalaBackendError):
    rpc_code = -32005
    public_message = "provider_error"


def payload_from_exception(exc: BaseException) -> JsonRpcErrorPayload:
    if isinstance(exc, ScalaBackendError):
        return exc.to_payload()
    return JsonRpcErrorPayload(
        code=JSON_RPC_INTERNAL_ERROR,
        message="internal_error",
        data={"detail": exc.__class__.__name__},
    )
