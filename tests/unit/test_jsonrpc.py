from scala_backend.jsonrpc import decode_message_line


def test_jsonrpc_parse_error_response_is_emitted() -> None:
    """깨진 JSON message가 parse error response로 변환되는지 확인한다."""
    message, error = decode_message_line(b"{bad json")

    assert message is None
    assert error == {
        "jsonrpc": "2.0",
        "id": None,
        "error": {"code": -32700, "message": "parse_error"},
    }


def test_jsonrpc_invalid_request_response_is_emitted() -> None:
    """method가 없는 JSON-RPC request가 invalid request response를 내는지 확인한다."""
    message, error = decode_message_line(b'["not", "an", "object"]')

    assert message is None
    assert error == {
        "jsonrpc": "2.0",
        "id": None,
        "error": {"code": -32600, "message": "invalid_request"},
    }
