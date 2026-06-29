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

// RPCError는 types에서 사용하는 타입을 정의한다.
type RPCError struct {
	Data    json.RawMessage
	Code    int
	Message string
}

// Error는 관련 동작을 처리한다.
func (e *RPCError) Error() string {
	return fmt.Sprintf("json-rpc error %d: %s", e.Code, e.Message)
}

// Unwrap는 관련 동작을 처리한다.
func (e *RPCError) Unwrap() error {
	return ErrRPC
}

// RequestID는 types에서 사용하는 타입을 정의한다.
type RequestID struct {
	raw json.RawMessage
}

// RequestIDFromString는 관련 동작을 처리한다.
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

// Valid는 관련 동작을 처리한다.
func (id RequestID) Valid() bool {
	return len(id.raw) > 0 && string(id.raw) != "null"
}

// String는 관련 동작을 처리한다.
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

// Inbound는 types에서 사용하는 타입을 정의한다.
type Inbound struct {
	Params json.RawMessage
	ID     RequestID
	Method string
}

// requestIDFromRaw는 관련 동작을 처리한다.
func requestIDFromRaw(raw json.RawMessage) RequestID {
	if len(raw) == 0 {
		return RequestID{}
	}
	copied := append(json.RawMessage(nil), raw...)
	return RequestID{raw: copied}
}
