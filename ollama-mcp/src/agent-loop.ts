/**
 * Agent Loop Driver for Agent Loop Dispatcher.
 * Orchestrates the prompt → parse → execute → loop cycle.
 */

import { AgentLoopOptions, AgentLoopResult, ToolCall } from './agent-types.js';
import { parseToolCalls } from './tool-call-parser.js';
import { executeTools } from './tool-executor.js';

// Default configuration
const DEFAULT_MAX_ITERATIONS = 10;
const DEFAULT_TIMEOUT_MS = 300000; // 5 minutes
const MAX_SAME_CALL_REPEATS = 3; // Circuit breaker: same call repeated
const MAX_CONSECUTIVE_ERRORS = 3; // Circuit breaker: consecutive errors
const MAX_CONTEXT_CHARS = 50000; // ~12k tokens, safe for most models

// System prompt template explaining available tools
const SYSTEM_PROMPT = `You have access to tools. To use a tool, output JSON on its own line:

{"name": "tool_name", "arguments": {"arg1": "value1"}}

Available tools:

1. ollama_request_draft
   Copy a source file to the sandbox for editing.
   Arguments: source_path (string), task_id (string)
   Returns: draft_path, original_hash

2. ollama_write_draft
   Write content to a draft file in the sandbox.
   Arguments: draft_path (string), content (string)
   Returns: success, new_hash

3. ollama_read_draft
   Read the current content of a draft file.
   Arguments: draft_path (string)
   Returns: content

4. ollama_submit_draft
   Submit the draft for Floor Manager review.
   Arguments: draft_path (string), original_path (string), task_id (string), change_summary (string)
   Returns: submission_path

Example:
{"name": "ollama_read_draft", "arguments": {"draft_path": "/path/to/file.draft"}}
Result: {"success": true, "content": "file contents here", "line_count": 42}

When finished with no more tool calls needed, provide your final answer as plain text.`;

/**
 * Run the agent loop.
 * 
 * @param prompt - The task prompt for the agent
 * @param ollamaRunFn - Function to call ollama_run (injected dependency)
 * @param options - Configuration options
 * @returns Agent loop result
 */
export async function runAgentLoop(
  prompt: string,
  ollamaRunFn: (model: string, prompt: string, options?: any) => Promise<{ stdout: string; stderr: string; exitCode: number; metadata?: any }>,
  options: AgentLoopOptions = {}
): Promise<AgentLoopResult> {
  const startTime = Date.now();
  const maxIterations = options.max_iterations ?? DEFAULT_MAX_ITERATIONS;
  const timeoutMs = options.timeout_ms ?? DEFAULT_TIMEOUT_MS;

  // Warn if no model specified, use a reasonable default
  if (!options.model) {
    console.warn('[agent-loop] No model specified, using qwen2.5-coder:7b');
  }
  const model = options.model ?? 'qwen2.5-coder:7b';

  const allToolCalls: ToolCall[] = [];
  let conversationContext = `${SYSTEM_PROMPT}\n\n${prompt}`;
  let iteration = 0;
  let consecutiveErrors = 0;
  const callHistory: string[] = []; // Track calls for loop detection

  console.error(`[agent-loop] Starting agent loop (max_iterations=${maxIterations}, timeout=${timeoutMs}ms)`);

  try {
    while (iteration < maxIterations) {
      iteration++;

      // Check timeout
      const elapsed = Date.now() - startTime;
      if (elapsed > timeoutMs) {
        return {
          success: false,
          final_output: '',
          iterations: iteration,
          tool_calls_made: allToolCalls,
          total_duration_ms: elapsed,
          error: `Timeout exceeded after ${elapsed}ms`,
        };
      }

      console.error(`[agent-loop] Iteration ${iteration}/${maxIterations}`);

      // Call model with current context
      const result = await ollamaRunFn(model, conversationContext, {
        timeout: Math.min(300000, timeoutMs - elapsed), // Leave buffer for processing
      });

      if (result.exitCode !== 0) {
        consecutiveErrors++;
        console.warn(`[agent-loop] Model execution failed (consecutive errors: ${consecutiveErrors})`);

        if (consecutiveErrors >= MAX_CONSECUTIVE_ERRORS) {
          return {
            success: false,
            final_output: result.stdout,
            iterations: iteration,
            tool_calls_made: allToolCalls,
            total_duration_ms: Date.now() - startTime,
            error: `Too many consecutive errors (${consecutiveErrors})`,
          };
        }

        // Retry with error feedback
        conversationContext += `\n\n[System Error: Model execution failed. Please try again or provide your final answer.]`;
        continue;
      }

      // Reset error counter on success
      consecutiveErrors = 0;

      // Parse tool calls from output
      const modelOutput = result.stdout;
      const toolCalls = parseToolCalls(modelOutput);

      // No tool calls means model is done
      if (toolCalls.length === 0) {
        console.error(`[agent-loop] No tool calls found, returning final output`);
        return {
          success: true,
          final_output: modelOutput,
          iterations: iteration,
          tool_calls_made: allToolCalls,
          total_duration_ms: Date.now() - startTime,
        };
      }

      console.error(`[agent-loop] Found ${toolCalls.length} tool call(s)`);

      // Circuit breaker: Check for infinite loops (same call repeated)
      for (const call of toolCalls) {
        const callSignature = `${call.name}:${JSON.stringify(call.arguments)}`;
        callHistory.push(callSignature);

        // Check last N calls
        const recentCalls = callHistory.slice(-MAX_SAME_CALL_REPEATS);
        if (recentCalls.length === MAX_SAME_CALL_REPEATS &&
          recentCalls.every(c => c === callSignature)) {
          return {
            success: false,
            final_output: modelOutput,
            iterations: iteration,
            tool_calls_made: allToolCalls,
            total_duration_ms: Date.now() - startTime,
            error: `Infinite loop detected: same call repeated ${MAX_SAME_CALL_REPEATS} times`,
          };
        }
      }

      // Execute tool calls
      const toolResults = await executeTools(toolCalls);
      allToolCalls.push(...toolCalls);

      // Format results as text to append to context
      let resultsText = '\n\n[Tool Results]\n';
      for (let i = 0; i < toolCalls.length; i++) {
        const call = toolCalls[i];
        const result = toolResults[i];
        resultsText += `\nTool: ${call.name}\n`;
        resultsText += `Result: ${JSON.stringify(result.output, null, 2)}\n`;
        if (result.error) {
          resultsText += `Error: ${result.error}\n`;
        }
      }

      // Append results to conversation context
      conversationContext += `\n${modelOutput}${resultsText}`;

      // Bound context size to prevent overflow
      if (conversationContext.length > MAX_CONTEXT_CHARS) {
        // Keep system prompt + recent context
        const systemPromptEnd = conversationContext.indexOf('\n\n') + 2;
        const systemPrompt = conversationContext.slice(0, systemPromptEnd);
        const recentContext = conversationContext.slice(-(MAX_CONTEXT_CHARS - systemPrompt.length));
        conversationContext = systemPrompt + '[...context truncated...]\n' + recentContext;
        console.error(`[agent-loop] Context truncated to ${conversationContext.length} chars`);
      }

      console.error(`[agent-loop] Executed ${toolResults.length} tool(s), continuing...`);
    }

    // Max iterations reached
    return {
      success: false,
      final_output: '',
      iterations: iteration,
      tool_calls_made: allToolCalls,
      total_duration_ms: Date.now() - startTime,
      error: `Max iterations (${maxIterations}) exceeded`,
    };

  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    console.error(`[agent-loop] Fatal error: ${errorMessage}`);

    return {
      success: false,
      final_output: '',
      iterations: iteration,
      tool_calls_made: allToolCalls,
      total_duration_ms: Date.now() - startTime,
      error: errorMessage,
    };
  }
}
