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

type RPCError struct {
	Data    json.RawMessage
	Code    int
	Message string
}

func (e *RPCError) Error() string {
	return fmt.Sprintf("json-rpc error %d: %s", e.Code, e.Message)
}

func (e *RPCError) Unwrap() error {
	return ErrRPC
}

type RequestID struct {
	raw json.RawMessage
}

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

func (id RequestID) Valid() bool {
	return len(id.raw) > 0 && string(id.raw) != "null"
}

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

type Inbound struct {
	Params json.RawMessage
	ID     RequestID
	Method string
}

func requestIDFromRaw(raw json.RawMessage) RequestID {
	if len(raw) == 0 {
		return RequestID{}
	}
	copied := append(json.RawMessage(nil), raw...)
	return RequestID{raw: copied}
}
