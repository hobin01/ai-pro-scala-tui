package backendrpc

import (
	"bufio"
	"context"
	"encoding/json"
	"net"
	"testing"
	"time"
)

// rpcServer는 test helpers test의 화면 출력과 상태 전이를 확인한다.
type rpcServer struct {
	listener net.Listener
	conn     net.Conn
	scanner  *bufio.Scanner
	accepted chan net.Conn
}

// wireRequest는 test helpers test의 화면 출력과 상태 전이를 확인한다.
type wireRequest struct {
	JSONRPC string          `json:"jsonrpc"`
	ID      json.RawMessage `json:"id"`
	Method  string          `json:"method"`
}

// wireResponse는 test helpers test의 화면 출력과 상태 전이를 확인한다.
type wireResponse struct {
	JSONRPC string          `json:"jsonrpc"`
	ID      json.RawMessage `json:"id"`
	Result  map[string]any  `json:"result"`
}

// startRPCServer는 test helpers test의 화면 출력과 상태 전이를 확인한다.
func startRPCServer(t *testing.T) (*rpcServer, string) {
	t.Helper()

	listener, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("listen: %v", err)
	}
	server := &rpcServer{
		listener: listener,
		accepted: make(chan net.Conn, 1),
	}
	go func() {
		conn, err := listener.Accept()
		if err != nil {
			close(server.accepted)
			return
		}
		server.accepted <- conn
	}()
	return server, listener.Addr().String()
}

// dialTestClient는 test helpers test의 화면 출력과 상태 전이를 확인한다.
func dialTestClient(t *testing.T, addr string) *Client {
	t.Helper()

	client, err := Dial(context.Background(), addr)
	if err != nil {
		t.Fatalf("Dial() error = %v", err)
	}
	return client
}

// ensureConn는 test helpers test의 화면 출력과 상태 전이를 확인한다.
func (s *rpcServer) ensureConn(t *testing.T) {
	t.Helper()

	if s.conn != nil {
		return
	}
	select {
	case conn, ok := <-s.accepted:
		if !ok {
			t.Fatalf("accept failed")
		}
		s.conn = conn
		s.scanner = bufio.NewScanner(conn)
	case <-time.After(time.Second):
		t.Fatalf("accept timed out")
	}
}

// readRequest는 test helpers test의 화면 출력과 상태 전이를 확인한다.
func (s *rpcServer) readRequest(t *testing.T) wireRequest {
	t.Helper()

	s.ensureConn(t)
	if !s.scanner.Scan() {
		t.Fatalf("read request: %v", s.scanner.Err())
	}
	var req wireRequest
	if err := json.Unmarshal(s.scanner.Bytes(), &req); err != nil {
		t.Fatalf("decode request: %v", err)
	}
	if req.JSONRPC != "2.0" || req.Method == "" || len(req.ID) == 0 {
		t.Fatalf("request = %+v, want jsonrpc/method/id", req)
	}
	return req
}

// readResponse는 test helpers test의 화면 출력과 상태 전이를 확인한다.
func (s *rpcServer) readResponse(t *testing.T) wireResponse {
	t.Helper()

	s.ensureConn(t)
	if !s.scanner.Scan() {
		t.Fatalf("read response: %v", s.scanner.Err())
	}
	var resp wireResponse
	if err := json.Unmarshal(s.scanner.Bytes(), &resp); err != nil {
		t.Fatalf("decode response: %v", err)
	}
	if resp.JSONRPC != "2.0" || len(resp.ID) == 0 {
		t.Fatalf("response = %+v, want jsonrpc/id", resp)
	}
	return resp
}

// writeMessage는 test helpers test의 화면 출력과 상태 전이를 확인한다.
func (s *rpcServer) writeMessage(t *testing.T, msg map[string]any) {
	t.Helper()

	s.ensureConn(t)
	data, err := json.Marshal(msg)
	if err != nil {
		t.Fatalf("marshal message: %v", err)
	}
	if _, err := s.conn.Write(append(data, '\n')); err != nil {
		t.Fatalf("write message: %v", err)
	}
}

// writeEchoResult는 test helpers test의 화면 출력과 상태 전이를 확인한다.
func writeEchoResult(t *testing.T, server *rpcServer, req wireRequest) {
	t.Helper()

	server.writeMessage(t, map[string]any{
		"jsonrpc": "2.0",
		"id":      req.ID,
		"result":  map[string]any{"value": req.Method + "-result"},
	})
}

// close는 test helpers test의 화면 출력과 상태 전이를 확인한다.
func (s *rpcServer) close(t *testing.T) {
	t.Helper()

	if s.conn != nil {
		if err := s.conn.Close(); err != nil {
			t.Logf("close conn: %v", err)
		}
	}
	if err := s.listener.Close(); err != nil {
		t.Logf("close listener: %v", err)
	}
}
