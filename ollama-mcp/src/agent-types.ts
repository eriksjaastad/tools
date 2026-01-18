/**
 * Types for Agent Loop Dispatcher.
 * Enables local models to execute tool calls in a loop.
 */

// Tool call parsed from model output
export interface ToolCall {
  name: string;
  arguments: Record<string, unknown>;
  thought?: string;  // Optional reasoning the model provided
}

// Result from executing a tool
export interface ToolResult {
  success: boolean;
  output: unknown;
  error?: string;
  duration_ms: number;
}

// Options for the agent loop
export interface AgentLoopOptions {
  max_iterations?: number;  // Default: 10
  timeout_ms?: number;      // Default: 300000 (5 min)
  model?: string;           // Override model selection
  task_type?: string;       // For smart routing
}

// Final result from agent loop
export interface AgentLoopResult {
  success: boolean;
  final_output: string;
  iterations: number;
  tool_calls_made: ToolCall[];
  total_duration_ms: number;
  error?: string;
}
