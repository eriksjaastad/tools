package mcp

import (
	"bufio"
	"encoding/json"
	"fmt"
	"io"
	"sync"

	"github.com/eriksjaastad/ollama-mcp-go/internal/logger"
)

// Tool represents an MCP tool definition.
type Tool struct {
	Name        string          `json:"name"`
	Description string          `json:"description"`
	InputSchema json.RawMessage `json:"inputSchema"`
	Handler     ToolHandler     `json:"-"`
}

// ToolHandler is a function that handles a tool call.
type ToolHandler func(params json.RawMessage) (any, error)

// Handler manages MCP protocol communication over stdio.
type Handler struct {
	tools map[string]Tool
	mu    sync.RWMutex
}

// NewHandler creates a new MCP handler.
func NewHandler() *Handler {
	return &Handler{
		tools: make(map[string]Tool),
	}
}

// RegisterTool registers a tool with the handler.
func (h *Handler) RegisterTool(tool Tool) {
	h.mu.Lock()
	defer h.mu.Unlock()
	h.tools[tool.Name] = tool
}

// Serve starts the stdio loop.
func (h *Handler) Serve(stdin io.Reader, stdout io.Writer) error {
	scanner := bufio.NewScanner(stdin)
	for scanner.Scan() {
		line := scanner.Bytes()
		if len(line) == 0 {
			continue
		}

		var req JSONRPCRequest
		if err := json.Unmarshal(line, &req); err != nil {
			h.sendError(stdout, nil, -32700, "Parse error", err.Error())
			continue
		}

		resp := h.handleRequest(req)
		if resp != nil {
			if err := h.sendResponse(stdout, resp); err != nil {
				logger.Error("Failed to send response", err)
			}
		}
	}
	return scanner.Err()
}

func (h *Handler) handleRequest(req JSONRPCRequest) *JSONRPCResponse {
	switch req.Method {
	case MethodInitialize:
		return &JSONRPCResponse{
			JSONRPC: JSONRPCVersion,
			ID:      req.ID,
			Result: map[string]any{
				"protocolVersion": "2024-11-05",
				"capabilities": map[string]any{
					"tools": map[string]any{},
				},
				"serverInfo": map[string]any{
					"name":    "ollama-mcp-go",
					"version": "1.0.0",
				},
			},
		}

	case MethodInitialized:
		return nil // Notification

	case MethodToolsList:
		h.mu.RLock()
		defer h.mu.RUnlock()
		tools := make([]Tool, 0, len(h.tools))
		for _, t := range h.tools {
			tools = append(tools, t)
		}
		return &JSONRPCResponse{
			JSONRPC: JSONRPCVersion,
			ID:      req.ID,
			Result: map[string]any{
				"tools": tools,
			},
		}

	case MethodToolsCall:
		var params struct {
			Name      string          `json:"name"`
			Arguments json.RawMessage `json:"arguments"`
		}
		if err := json.Unmarshal(req.Params, &params); err != nil {
			return h.makeError(req.ID, -32602, "Invalid params", err.Error())
		}

		h.mu.RLock()
		tool, ok := h.tools[params.Name]
		h.mu.RUnlock()

		if !ok {
			return h.makeError(req.ID, -32601, fmt.Sprintf("Tool not found: %s", params.Name), nil)
		}

		result, err := tool.Handler(params.Arguments)
		if err != nil {
			return &JSONRPCResponse{
				JSONRPC: JSONRPCVersion,
				ID:      req.ID,
				Result: map[string]any{
					"content": []map[string]any{
						{
							"type": "text",
							"text": err.Error(),
						},
					},
					"isError": true,
				},
			}
		}

		return &JSONRPCResponse{
			JSONRPC: JSONRPCVersion,
			ID:      req.ID,
			Result:  result,
		}

	default:
		if req.ID != nil {
			return h.makeError(req.ID, -32601, "Method not found", req.Method)
		}
		return nil
	}
}

func (h *Handler) sendResponse(stdout io.Writer, resp *JSONRPCResponse) error {
	data, err := json.Marshal(resp)
	if err != nil {
		return err
	}
	_, err = fmt.Fprintf(stdout, "%s\n", data)
	return err
}

func (h *Handler) sendError(stdout io.Writer, id any, code int, message string, data any) {
	resp := h.makeError(id, code, message, data)
	_ = h.sendResponse(stdout, resp)
}

func (h *Handler) makeError(id any, code int, message string, data any) *JSONRPCResponse {
	return &JSONRPCResponse{
		JSONRPC: JSONRPCVersion,
		ID:      id,
		Error: &JSONRPCError{
			Code:    code,
			Message: message,
			Data:    data,
		},
	}
}
