package backendrpc

import (
	"bufio"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"strconv"
	"sync"
	"sync/atomic"
)

type Client struct {
	conn net.Conn

	incoming chan Inbound
	done     chan struct{}
	closing  chan struct{}

	writeMu sync.Mutex

	pendingMu sync.Mutex
	pending   map[string]chan response

	nextID    atomic.Int64
	closed    atomic.Bool
	closeOnce sync.Once
	closeErr  error
}

type response struct {
	err    error
	result json.RawMessage
}

func Dial(ctx context.Context, addr string) (*Client, error) {
	var dialer net.Dialer
	conn, err := dialer.DialContext(ctx, "tcp", addr)
	if err != nil {
		return nil, fmt.Errorf("dial backend rpc: %w", err)
	}
	client := &Client{
		conn:     conn,
		incoming: make(chan Inbound, 16),
		done:     make(chan struct{}),
		closing:  make(chan struct{}),
		pending:  make(map[string]chan response),
	}
	go client.readLoop()
	return client, nil
}

func (c *Client) Incoming() <-chan Inbound {
	return c.incoming
}

func (c *Client) Call(ctx context.Context, method string, params any, result any) error {
	if params == nil {
		params = map[string]any{}
	}
	id := c.nextID.Add(1)
	rawID := json.RawMessage(strconv.FormatInt(id, 10))
	key := string(rawID)
	done := make(chan response, 1)
	c.addPending(key, done)

	err := c.send(ctx, outboundMessage{
		JSONRPC: "2.0",
		ID:      rawID,
		Method:  method,
		Params:  params,
	})
	if err != nil {
		c.removePending(key)
		return fmt.Errorf("send %s request: %w", method, err)
	}

	select {
	case got := <-done:
		if got.err != nil {
			return fmt.Errorf("call %s: %w", method, got.err)
		}
		if result == nil {
			return nil
		}
		if err := json.Unmarshal(got.result, result); err != nil {
			return fmt.Errorf("decode %s result: %w", method, err)
		}
		return nil
	case <-ctx.Done():
		c.removePending(key)
		return fmt.Errorf("call %s: %w", method, ctx.Err())
	}
}

func (c *Client) Respond(ctx context.Context, id RequestID, result any) error {
	if !id.Valid() {
		return ErrInvalidID
	}
	if result == nil {
		result = map[string]any{}
	}
	err := c.send(ctx, outboundMessage{
		JSONRPC: "2.0",
		ID:      id.raw,
		Result:  result,
	})
	if err != nil {
		return fmt.Errorf("send response: %w", err)
	}
	return nil
}

func (c *Client) RespondError(ctx context.Context, id RequestID, rpcErr *RPCError) error {
	if !id.Valid() {
		return ErrInvalidID
	}
	if rpcErr == nil {
		return fmt.Errorf("nil rpc error: %w", ErrRPC)
	}
	err := c.send(ctx, outboundMessage{
		JSONRPC: "2.0",
		ID:      id.raw,
		Error: &rpcErrorPayload{
			Code:    rpcErr.Code,
			Message: rpcErr.Message,
			Data:    rpcErr.Data,
		},
	})
	if err != nil {
		return fmt.Errorf("send error response: %w", err)
	}
	return nil
}

func (c *Client) Close() error {
	c.closeOnce.Do(func() {
		c.closed.Store(true)
		close(c.closing)
		c.closeErr = c.conn.Close()
		<-c.done
	})
	return c.closeErr
}

func (c *Client) readLoop() {
	defer close(c.done)
	defer close(c.incoming)

	scanner := bufio.NewScanner(c.conn)
	scanner.Buffer(make([]byte, 0, 64*1024), maxMessageBytes)
	for scanner.Scan() {
		c.handleLine(scanner.Bytes())
	}
	if c.closed.Load() {
		c.failPending(ErrClosed)
		return
	}
	if err := scanner.Err(); err != nil {
		c.failPending(fmt.Errorf("read backend rpc: %w", err))
		return
	}
	c.failPending(fmt.Errorf("backend rpc closed: %w", io.EOF))
}

func (c *Client) handleLine(line []byte) {
	var msg wireMessage
	if err := json.Unmarshal(line, &msg); err != nil {
		return
	}
	if msg.Method != "" {
		c.emitInbound(msg)
		return
	}
	c.completePending(msg)
}

func (c *Client) emitInbound(msg wireMessage) {
	inbound := Inbound{
		Method: msg.Method,
		Params: append(json.RawMessage(nil), msg.Params...),
		ID:     requestIDFromRaw(msg.ID),
	}
	select {
	case c.incoming <- inbound:
	case <-c.closing:
	}
}

func (c *Client) completePending(msg wireMessage) {
	key := string(msg.ID)
	if key == "" {
		return
	}
	done := c.removePending(key)
	if done == nil {
		return
	}
	if msg.Error != nil {
		done <- response{err: &RPCError{
			Code:    msg.Error.Code,
			Message: msg.Error.Message,
			Data:    append(json.RawMessage(nil), msg.Error.Data...),
		}}
		return
	}
	done <- response{result: append(json.RawMessage(nil), msg.Result...)}
}

func (c *Client) send(ctx context.Context, msg outboundMessage) error {
	select {
	case <-ctx.Done():
		return ctx.Err()
	case <-c.closing:
		return ErrClosed
	default:
	}
	data, err := json.Marshal(msg)
	if err != nil {
		return fmt.Errorf("marshal message: %w", err)
	}
	data = append(data, '\n')

	c.writeMu.Lock()
	defer c.writeMu.Unlock()

	select {
	case <-ctx.Done():
		return ctx.Err()
	case <-c.closing:
		return ErrClosed
	default:
	}
	if _, err := c.conn.Write(data); err != nil {
		return fmt.Errorf("write message: %w", err)
	}
	return nil
}

func (c *Client) addPending(key string, done chan response) {
	c.pendingMu.Lock()
	defer c.pendingMu.Unlock()
	c.pending[key] = done
}

func (c *Client) removePending(key string) chan response {
	c.pendingMu.Lock()
	defer c.pendingMu.Unlock()
	done := c.pending[key]
	delete(c.pending, key)
	return done
}

func (c *Client) failPending(err error) {
	c.pendingMu.Lock()
	defer c.pendingMu.Unlock()
	for key, done := range c.pending {
		delete(c.pending, key)
		done <- response{err: err}
	}
}
