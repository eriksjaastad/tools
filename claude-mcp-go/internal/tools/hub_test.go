package tools

import (
	"fmt"
	"os"
	"path/filepath"
	"sync"
	"testing"
	"time"
)

func TestHubStateManagement(t *testing.T) {
	tempDir := t.TempDir()
	stateFile := filepath.Join(tempDir, "hub_state.json")

	hub := &MessageHub{
		stateFile: stateFile,
	}

	t.Run("Create empty state when file does not exist", func(t *testing.T) {
		state := hub.loadState()
		if len(state.Messages) != 0 || len(state.Agents) != 0 {
			t.Errorf("Expected empty state, got messages:%d, agents:%d", len(state.Messages), len(state.Agents))
		}
	})

	t.Run("Persist messages across saves", func(t *testing.T) {
		msg := Message{
			ID:        "1",
			Type:      "TEST",
			From:      "a",
			To:        "b",
			Payload:   map[string]interface{}{},
			Timestamp: time.Now().UTC().Format(time.RFC3339),
		}
		state := HubState{
			Messages:   []Message{msg},
			Heartbeats: make(map[string]Heartbeat),
			Agents:     []string{"a", "b"},
		}

		err := hub.saveState(state)
		if err != nil {
			t.Fatalf("Failed to save state: %v", err)
		}

		loaded := hub.loadState()
		if len(loaded.Messages) != 1 || loaded.Messages[0].ID != "1" {
			t.Errorf("Loaded state does not match saved state")
		}
	})

	t.Run("Handle corrupted state file gracefully", func(t *testing.T) {
		os.WriteFile(stateFile, []byte("not-json"), 0644)
		state := hub.loadState()
		if len(state.Messages) != 0 {
			t.Errorf("Expected empty state for corrupted file, got messages:%d", len(state.Messages))
		}
	})
}

func TestHubLogic(t *testing.T) {
	tempDir := t.TempDir()
	hub := &MessageHub{
		stateFile: filepath.Join(tempDir, "hub_state.json"),
	}

	t.Run("hub_connect registers agent", func(t *testing.T) {
		hub.Connect("agent-1")
		state := hub.loadState()
		found := false
		for _, a := range state.Agents {
			if a == "agent-1" {
				found = true
				break
			}
		}
		if !found {
			t.Errorf("Agent-1 not registered")
		}
	})

	t.Run("hub_send_message adds message to state", func(t *testing.T) {
		msg := Message{Type: "INFO", From: "m1", To: "m2", Payload: "hello"}
		id := hub.SendMessage(msg)
		if id == "" {
			t.Errorf("Message ID was not generated")
		}
		state := hub.loadState()
		if len(state.Messages) == 0 || state.Messages[len(state.Messages)-1].To != "m2" {
			t.Errorf("Message not found in state")
		}
	})

	t.Run("hub_receive_messages filters correctly", func(t *testing.T) {
		hub.SendMessage(Message{From: "x", To: "agent-1", Timestamp: "2024-01-01T10:00:00Z"})
		hub.SendMessage(Message{From: "x", To: "agent-2", Timestamp: "2024-01-01T11:00:00Z"})
		hub.SendMessage(Message{From: "x", To: "agent-1", Timestamp: "2024-01-01T12:00:00Z"})

		msgs := hub.ReceiveMessages("agent-1", "")
		if len(msgs) != 2 {
			t.Errorf("Expected 2 messages for agent-1, got %d", len(msgs))
		}

		msgsSince := hub.ReceiveMessages("agent-1", "2024-01-01T11:00:00Z")
		if len(msgsSince) != 1 {
			t.Errorf("Expected 1 message for agent-1 since 11:00, got %d", len(msgsSince))
		}
	})

	t.Run("hub_heartbeat updates heartbeat map", func(t *testing.T) {
		hub.UpdateHeartbeat("agent-1", "processing", "2024-05-20T12:00:00Z")
		state := hub.loadState()
		hb, ok := state.Heartbeats["agent-1"]
		if !ok || hb.Progress != "processing" {
			t.Errorf("Heartbeat not updated correctly")
		}
	})

	t.Run("Atomic file write (temp file + rename)", func(t *testing.T) {
		state := hub.loadState()
		hub.saveState(state)

		files, _ := os.ReadDir(tempDir)
		for _, f := range files {
			if filepath.Ext(f.Name()) == ".tmp" {
				t.Errorf("Found leaked temp file: %s", f.Name())
			}
		}
	})

	t.Run("Mutex prevents race conditions", func(t *testing.T) {
		var wg sync.WaitGroup
		numGorr := 100
		wg.Add(numGorr)
		for i := 0; i < numGorr; i++ {
			go func(val int) {
				defer wg.Done()
				hub.Connect(fmt.Sprintf("agent-%d", val))
			}(i)
		}
		wg.Wait()
		state := hub.loadState()
		if len(state.Agents) < numGorr {
			// In a fresh temp dir, we expect exactly numGorr agents
			t.Errorf("Expected at least %d agents, got %d", numGorr, len(state.Agents))
		}
	})
}
