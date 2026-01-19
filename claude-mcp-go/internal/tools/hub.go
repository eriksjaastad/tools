package tools

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sync"
	"time"

	"github.com/google/uuid"
	"github.com/mark3labs/mcp-go/mcp"
	"github.com/mark3labs/mcp-go/server"
)

type Message struct {
	ID        string      `json:"id"`
	Type      string      `json:"type"`
	From      string      `json:"from"`
	To        string      `json:"to"`
	Payload   interface{} `json:"payload"`
	Timestamp string      `json:"timestamp"`
}

type Heartbeat struct {
	AgentID   string `json:"agent_id"`
	Progress  string `json:"progress"`
	Timestamp string `json:"timestamp"`
}

type HubState struct {
	Messages   []Message            `json:"messages"`
	Heartbeats map[string]Heartbeat `json:"heartbeats"`
	Agents     []string             `json:"agents"`
}

type MessageHub struct {
	mu        sync.Mutex
	stateFile string
}

func NewMessageHub() *MessageHub {
	// Check for environment variable first
	stateDir := os.Getenv("HUB_STATE_DIR")
	if stateDir == "" {
		cwd, err := os.Getwd()
		if err != nil {
			cwd = "."
		}
		stateDir = filepath.Join(cwd, "_handoff")
	}
	return &MessageHub{
		stateFile: filepath.Join(stateDir, "hub_state.json"),
	}
}

func (h *MessageHub) loadState() HubState {
	state := HubState{
		Messages:   []Message{},
		Heartbeats: make(map[string]Heartbeat),
		Agents:     []string{},
	}

	if _, err := os.Stat(h.stateFile); os.IsNotExist(err) {
		return state
	}

	data, err := os.ReadFile(h.stateFile)
	if err != nil {
		return state
	}

	err = json.Unmarshal(data, &state)
	if err != nil {
		return state
	}

	if state.Heartbeats == nil {
		state.Heartbeats = make(map[string]Heartbeat)
	}

	return state
}

func (h *MessageHub) saveState(state HubState) error {
	dir := filepath.Dir(h.stateFile)
	if err := os.MkdirAll(dir, 0755); err != nil {
		return err
	}

	data, err := json.MarshalIndent(state, "", "  ")
	if err != nil {
		return err
	}

	// Atomic write
	tmpFile := fmt.Sprintf("%s.%d.tmp", h.stateFile, time.Now().UnixNano())
	if err := os.WriteFile(tmpFile, data, 0644); err != nil {
		return err
	}

	return os.Rename(tmpFile, h.stateFile)
}

// Handler implementations for testing

func (h *MessageHub) Connect(agentID string) {
	h.mu.Lock()
	defer h.mu.Unlock()
	state := h.loadState()
	found := false
	for _, a := range state.Agents {
		if a == agentID {
			found = true
			break
		}
	}
	if !found {
		state.Agents = append(state.Agents, agentID)
		h.saveState(state)
	}
}

func (h *MessageHub) SendMessage(msg Message) string {
	if msg.ID == "" {
		msg.ID = uuid.New().String()
	}
	if msg.Timestamp == "" {
		msg.Timestamp = time.Now().UTC().Format(time.RFC3339)
	}

	h.mu.Lock()
	defer h.mu.Unlock()

	state := h.loadState()
	state.Messages = append(state.Messages, msg)
	h.saveState(state)
	return msg.ID
}

func (h *MessageHub) ReceiveMessages(agentID string, since string) []Message {
	h.mu.Lock()
	defer h.mu.Unlock()

	state := h.loadState()
	var filtered []Message
	var sinceDate time.Time
	if since != "" {
		sinceDate, _ = time.Parse(time.RFC3339, since)
	}

	for _, m := range state.Messages {
		if m.To == agentID {
			if since != "" {
				mDate, _ := time.Parse(time.RFC3339, m.Timestamp)
				if mDate.After(sinceDate) {
					filtered = append(filtered, m)
				}
			} else {
				filtered = append(filtered, m)
			}
		}
	}
	return filtered
}

func (h *MessageHub) UpdateHeartbeat(agentID string, progress string, timestamp string) {
	if timestamp == "" {
		timestamp = time.Now().UTC().Format(time.RFC3339)
	}

	h.mu.Lock()
	defer h.mu.Unlock()

	state := h.loadState()
	state.Heartbeats[agentID] = Heartbeat{
		AgentID:   agentID,
		Progress:  progress,
		Timestamp: timestamp,
	}
	h.saveState(state)
}

func RegisterHubTools(s *server.MCPServer) {
	hub := NewMessageHub()

	// hub_connect
	s.AddTool(mcp.NewTool("hub_connect",
		mcp.WithDescription("Register agent with the hub"),
		mcp.WithString("agent_id", mcp.Required(), mcp.Description("Agent ID to register")),
	), func(ctx context.Context, request mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		args, _ := request.Params.Arguments.(map[string]interface{})
		agentID, _ := args["agent_id"].(string)
		hub.Connect(agentID)
		return mcp.NewToolResultStructuredOnly(map[string]interface{}{"success": true}), nil
	})

	// hub_send_message
	s.AddTool(mcp.NewTool("hub_send_message",
		mcp.WithDescription("Send message to another agent"),
		mcp.WithObject("message", mcp.Required(), mcp.Description("Message object")),
	), func(ctx context.Context, request mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		args, _ := request.Params.Arguments.(map[string]interface{})
		rawMsg, _ := args["message"].(map[string]interface{})

		// Use type assertions to safely extract string values
		msg := Message{
			Payload: rawMsg["payload"],
		}
		if v, ok := rawMsg["id"].(string); ok {
			msg.ID = v
		}
		if v, ok := rawMsg["type"].(string); ok {
			msg.Type = v
		}
		if v, ok := rawMsg["from"].(string); ok {
			msg.From = v
		}
		if v, ok := rawMsg["to"].(string); ok {
			msg.To = v
		}
		if v, ok := rawMsg["timestamp"].(string); ok {
			msg.Timestamp = v
		}

		id := hub.SendMessage(msg)

		return mcp.NewToolResultStructuredOnly(map[string]interface{}{
			"success": true,
			"id":      id,
		}), nil
	})

	// hub_receive_messages
	s.AddTool(mcp.NewTool("hub_receive_messages",
		mcp.WithDescription("Check inbox for pending messages"),
		mcp.WithString("agent_id", mcp.Required(), mcp.Description("Agent ID to check messages for")),
		mcp.WithString("since", mcp.Description("ISO timestamp to filter messages")),
	), func(ctx context.Context, request mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		args, _ := request.Params.Arguments.(map[string]interface{})
		agentID, _ := args["agent_id"].(string)
		since, _ := args["since"].(string)

		messages := hub.ReceiveMessages(agentID, since)

		return mcp.NewToolResultStructuredOnly(map[string]interface{}{
			"success":  true,
			"messages": messages,
		}), nil
	})

	// hub_heartbeat
	s.AddTool(mcp.NewTool("hub_heartbeat",
		mcp.WithDescription("Signal agent is alive"),
		mcp.WithString("agent_id", mcp.Required(), mcp.Description("Agent ID")),
		mcp.WithString("progress", mcp.Required(), mcp.Description("Current progress status")),
		mcp.WithString("timestamp", mcp.Description("ISO timestamp")),
	), func(ctx context.Context, request mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		args, _ := request.Params.Arguments.(map[string]interface{})
		agentID, _ := args["agent_id"].(string)
		progress, _ := args["progress"].(string)
		timestamp, _ := args["timestamp"].(string)

		hub.UpdateHeartbeat(agentID, progress, timestamp)

		return mcp.NewToolResultStructuredOnly(map[string]interface{}{"success": true}), nil
	})

	// hub_send_answer
	s.AddTool(mcp.NewTool("hub_send_answer",
		mcp.WithDescription("Answer a previous question"),
		mcp.WithString("from", mcp.Required(), mcp.Description("Agent ID answering")),
		mcp.WithObject("payload", mcp.Required(), mcp.Description("Answer payload (question_id, selected_option)")),
	), func(ctx context.Context, request mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		args, _ := request.Params.Arguments.(map[string]interface{})
		from, _ := args["from"].(string)
		payload, _ := args["payload"].(map[string]interface{})

		msg := Message{
			Type:    "ANSWER",
			From:    from,
			To:      "super_manager",
			Payload: payload,
		}
		id := hub.SendMessage(msg)

		return mcp.NewToolResultStructuredOnly(map[string]interface{}{
			"success": true,
			"id":      id,
		}), nil
	})

	// hub_get_all_messages
	s.AddTool(mcp.NewTool("hub_get_all_messages",
		mcp.WithDescription("Get all messages (debug)"),
	), func(ctx context.Context, request mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		hub.mu.Lock()
		defer hub.mu.Unlock()

		state := hub.loadState()
		return mcp.NewToolResultStructuredOnly(map[string]interface{}{
			"messages": state.Messages,
		}), nil
	})
}
