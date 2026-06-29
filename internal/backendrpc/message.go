package backendrpc

import "encoding/json"

const maxMessageBytes = 1_048_576

// wireMessage는 message에서 사용하는 타입을 정의한다.
type wireMessage struct {
	Params  json.RawMessage  `json:"params,omitempty"`
	Result  json.RawMessage  `json:"result,omitempty"`
	Error   *rpcErrorPayload `json:"error,omitempty"`
	JSONRPC string           `json:"jsonrpc"`
	ID      json.RawMessage  `json:"id,omitempty"`
	Method  string           `json:"method,omitempty"`
}

// outboundMessage는 message에서 사용하는 타입을 정의한다.
type outboundMessage struct {
	Params  any              `json:"params,omitempty"`
	Result  any              `json:"result,omitempty"`
	Error   *rpcErrorPayload `json:"error,omitempty"`
	JSONRPC string           `json:"jsonrpc"`
	ID      json.RawMessage  `json:"id,omitempty"`
	Method  string           `json:"method,omitempty"`
}

// rpcErrorPayload는 message에서 사용하는 타입을 정의한다.
type rpcErrorPayload struct {
	Data    json.RawMessage `json:"data,omitempty"`
	Code    int             `json:"code"`
	Message string          `json:"message"`
}
