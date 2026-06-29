package backendrpc

import (
	"encoding/json"
	"errors"
	"fmt"
)

var (
	ErrRPC       = errors.New("backendrpc: json-rpc error")
	ErrClosed    = errors.New("backendrpc: client closed")
	ErrInvalidID = errors.New("backendrpc: invalid request id")
)

// RPCError는 JSON-RPC error 객체를 Go error로 보존한다.
type RPCError struct {
	Data    json.RawMessage
	Code    int
	Message string
}

// Error는 RPC code와 message를 포함한 error 문자열을 만든다.
func (e *RPCError) Error() string {
	return fmt.Sprintf("json-rpc error %d: %s", e.Code, e.Message)
}

// Unwrap은 errors.Is로 JSON-RPC 오류를 식별하게 한다.
func (e *RPCError) Unwrap() error {
	return ErrRPC
}

// RequestID는 서버 발신 request에 응답할 raw JSON-RPC id다.
type RequestID struct {
	raw json.RawMessage
}

// RequestIDFromString는 문자열 id를 JSON-RPC id raw 값으로 보관한다.
func RequestIDFromString(value string) RequestID {
	if value == "" {
		return RequestID{}
	}
	var raw json.RawMessage
	if json.Valid([]byte(value)) {
		raw = json.RawMessage(value)
	} else {
		encoded, err := json.Marshal(value)
		if err != nil {
			return RequestID{}
		}
		raw = encoded
	}
	return RequestID{raw: append(json.RawMessage(nil), raw...)}
}

// Valid는 응답 가능한 JSON-RPC id가 들어 있는지 확인한다.
func (id RequestID) Valid() bool {
	return len(id.raw) > 0 && string(id.raw) != "null"
}

// String은 raw JSON-RPC id를 로그와 queue에 쓸 문자열로 풀어낸다.
func (id RequestID) String() string {
	if !id.Valid() {
		return ""
	}
	var decoded any
	if err := json.Unmarshal(id.raw, &decoded); err != nil {
		return string(id.raw)
	}
	return fmt.Sprint(decoded)
}

// Inbound는 서버 발신 method, params, request id를 app 계층에 전달한다.
type Inbound struct {
	Params json.RawMessage
	ID     RequestID
	Method string
}

// requestIDFromRaw는 수신한 raw id를 복사해 RequestID로 감싼다.
func requestIDFromRaw(raw json.RawMessage) RequestID {
	if len(raw) == 0 {
		return RequestID{}
	}
	copied := append(json.RawMessage(nil), raw...)
	return RequestID{raw: copied}
}
