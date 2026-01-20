package tools

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/eriksjaastad/ollama-mcp-go/internal/ollama"
)

// RunHandler provides methods for Ollama run operations.
type RunHandler struct {
	client *ollama.Client
}

// NewRunHandler creates a new RunHandler.
func NewRunHandler(client *ollama.Client) *RunHandler {
	return &RunHandler{client: client}
}

// RunInput represents the input for ollama_run.
type RunInput struct {
	Model   string         `json:"model"`
	Prompt  string         `json:"prompt"`
	System  string         `json:"system,omitempty"`
	Options map[string]any `json:"options,omitempty"`
}

// Run handles the ollama_run tool.
func (h *RunHandler) Run(params json.RawMessage) (any, error) {
	var input RunInput
	if err := json.Unmarshal(params, &input); err != nil {
		return nil, err
	}

	if input.Model == "" {
		return nil, fmt.Errorf("model is required")
	}

	req := ollama.GenerateRequest{
		Model:   input.Model,
		Prompt:  input.Prompt,
		System:  input.System,
		Options: input.Options,
	}

	start := time.Now()
	resp, err := h.client.Generate(context.TODO(), req) // Using context.TODO() as per lint guidance
	if err != nil {
		return nil, err
	}

	return map[string]any{
		"response":       resp.Response,
		"model":          resp.Model,
		"total_duration": time.Since(start).Milliseconds(),
	}, nil
}

// RunManyInput represents the input for ollama_run_many.
type RunManyInput struct {
	Requests       []RunInput `json:"requests"`
	MaxConcurrency int        `json:"maxConcurrency"`
}

// RunMany handles the ollama_run_many tool.
func (h *RunHandler) RunMany(params json.RawMessage) (any, error) {
	var input RunManyInput
	if err := json.Unmarshal(params, &input); err != nil {
		return nil, err
	}

	ollamaReqs := make([]ollama.GenerateRequest, len(input.Requests))
	for i, r := range input.Requests {
		ollamaReqs[i] = ollama.GenerateRequest{
			Model:   r.Model,
			Prompt:  r.Prompt,
			System:  r.System,
			Options: r.Options,
		}
	}

	resps, err := h.client.RunMany(context.TODO(), ollamaReqs, input.MaxConcurrency)
	if err != nil {
		return nil, err
	}

	results := make([]map[string]any, len(resps))
	for i, r := range resps {
		results[i] = map[string]any{
			"response": r.Response,
			"model":    r.Model,
			"index":    i,
		}
	}

	return map[string]any{
		"responses": results,
	}, nil
}

// ListModels returns available Ollama models.
func (h *RunHandler) ListModels(params json.RawMessage) (any, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	resp, err := h.client.ListModels(ctx)
	if err != nil {
		return nil, fmt.Errorf("failed to list models: %w", err)
	}

	return resp.Models, nil
}
