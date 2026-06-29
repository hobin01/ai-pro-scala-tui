package backendrpc

import (
	"context"
	"errors"
	"testing"
	"time"
)

// TestClient_Call_matches_response_by_id는 client test의 화면 출력과 상태 전이를 확인한다.
func TestClient_Call_matches_response_by_id(t *testing.T) {
	server, addr := startRPCServer(t)
	defer server.close(t)

	client := dialTestClient(t, addr)
	defer client.Close()

	firstDone := make(chan callResult, 1)
	secondDone := make(chan callResult, 1)

	go callEcho(t, client, "first", firstDone)
	go callEcho(t, client, "second", secondDone)

	firstReq := server.readRequest(t)
	secondReq := server.readRequest(t)
	writeEchoResult(t, server, firstReq)
	writeEchoResult(t, server, secondReq)

	requireCallResult(t, firstDone, "first-result")
	requireCallResult(t, secondDone, "second-result")
}

// TestClient_Incoming_emits_notifications_and_server_requests는 client test의 화면 출력과 상태 전이를 확인한다.
func TestClient_Incoming_emits_notifications_and_server_requests(t *testing.T) {
	server, addr := startRPCServer(t)
	defer server.close(t)

	client := dialTestClient(t, addr)
	defer client.Close()

	server.writeMessage(t, map[string]any{
		"jsonrpc": "2.0",
		"method":  "progress",
		"params":  map[string]any{"message": "profiling"},
	})
	server.writeMessage(t, map[string]any{
		"jsonrpc": "2.0",
		"id":      "srv-1",
		"method":  "feedback.request",
		"params":  map[string]any{"run_id": "run-1"},
	})

	notification := receiveInbound(t, client.Incoming())
	request := receiveInbound(t, client.Incoming())
	if err := client.Respond(context.Background(), request.ID, map[string]any{"decision": "approve"}); err != nil {
		t.Fatalf("Respond() error = %v", err)
	}

	response := server.readResponse(t)

	if notification.Method != "progress" {
		t.Fatalf("notification method = %q, want progress", notification.Method)
	}
	if notification.ID.Valid() {
		t.Fatalf("notification ID is valid, want invalid")
	}
	if request.Method != "feedback.request" {
		t.Fatalf("request method = %q, want feedback.request", request.Method)
	}
	if !request.ID.Valid() {
		t.Fatalf("request ID is invalid, want valid")
	}
	if string(response.ID) != `"srv-1"` {
		t.Fatalf("response id = %s, want %q", response.ID, `"srv-1"`)
	}
	if got := response.Result["decision"]; got != "approve" {
		t.Fatalf("response decision = %v, want approve", got)
	}
}

// TestClient_Call_wraps_json_rpc_errors는 client test의 화면 출력과 상태 전이를 확인한다.
func TestClient_Call_wraps_json_rpc_errors(t *testing.T) {
	server, addr := startRPCServer(t)
	defer server.close(t)

	client := dialTestClient(t, addr)
	defer client.Close()

	done := make(chan error, 1)

	go func() {
		var result map[string]any
		done <- client.Call(context.Background(), "settings.get", map[string]any{}, &result)
	}()

	req := server.readRequest(t)
	server.writeMessage(t, map[string]any{
		"jsonrpc": "2.0",
		"id":      req.ID,
		"error": map[string]any{
			"code":    -32602,
			"message": "invalid_params",
			"data":    map[string]any{"detail": "bad field"},
		},
	})
	err := receiveErr(t, done)

	if !errors.Is(err, ErrRPC) {
		t.Fatalf("Call() error = %v, want ErrRPC", err)
	}
	var rpcErr *RPCError
	if !errors.As(err, &rpcErr) {
		t.Fatalf("Call() error = %T, want *RPCError", err)
	}
	if rpcErr.Code != -32602 || rpcErr.Message != "invalid_params" {
		t.Fatalf("RPCError = {Code:%d Message:%q}, want {-32602 invalid_params}", rpcErr.Code, rpcErr.Message)
	}
}

// TestClient_Close_closes_incoming_channel는 client test의 화면 출력과 상태 전이를 확인한다.
func TestClient_Close_closes_incoming_channel(t *testing.T) {
	server, addr := startRPCServer(t)
	defer server.close(t)

	client := dialTestClient(t, addr)

	if err := client.Close(); err != nil {
		t.Fatalf("Close() error = %v", err)
	}

	select {
	case _, ok := <-client.Incoming():
		if ok {
			t.Fatalf("Incoming() channel open after Close()")
		}
	case <-time.After(time.Second):
		t.Fatalf("Incoming() channel did not close")
	}
}

// callResult는 client test의 화면 출력과 상태 전이를 확인한다.
type callResult struct {
	value string
	err   error
}

// callEcho는 client test의 화면 출력과 상태 전이를 확인한다.
func callEcho(t *testing.T, client *Client, method string, done chan<- callResult) {
	t.Helper()

	ctx, cancel := context.WithTimeout(context.Background(), time.Second)
	defer cancel()

	var result struct {
		Value string `json:"value"`
	}
	err := client.Call(ctx, method, map[string]any{}, &result)
	done <- callResult{value: result.Value, err: err}
}

// requireCallResult는 client test의 화면 출력과 상태 전이를 확인한다.
func requireCallResult(t *testing.T, ch <-chan callResult, want string) {
	t.Helper()

	select {
	case got := <-ch:
		if got.err != nil {
			t.Fatalf("Call() error = %v", got.err)
		}
		if got.value != want {
			t.Fatalf("Call() value = %q, want %q", got.value, want)
		}
	case <-time.After(time.Second):
		t.Fatalf("Call() timed out")
	}
}

// receiveInbound는 client test의 화면 출력과 상태 전이를 확인한다.
func receiveInbound(t *testing.T, ch <-chan Inbound) Inbound {
	t.Helper()

	select {
	case msg, ok := <-ch:
		if !ok {
			t.Fatalf("Incoming() closed")
		}
		return msg
	case <-time.After(time.Second):
		t.Fatalf("Incoming() timed out")
	}
	return Inbound{}
}

// receiveErr는 client test의 화면 출력과 상태 전이를 확인한다.
func receiveErr(t *testing.T, ch <-chan error) error {
	t.Helper()

	select {
	case err := <-ch:
		return err
	case <-time.After(time.Second):
		t.Fatalf("error receive timed out")
	}
	return nil
}
