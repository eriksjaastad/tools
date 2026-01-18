/**
 * Tool Executor for Agent Loop Dispatcher.
 * Routes parsed tool calls to existing handlers.
 */

import { ToolCall, ToolResult } from './agent-types.js';
import { requestDraft, writeDraft, readDraft, submitDraft } from './draft-tools.js';
import {
  RequestDraftInput,
  WriteDraftInput,
  ReadDraftInput,
  SubmitDraftInput,
} from './draft-types.js';

/**
 * Execute a single tool call.
 * Routes to the appropriate handler and wraps result.
 * 
 * @param toolCall - Parsed tool call
 * @returns Structured tool result
 */
export async function executeTool(toolCall: ToolCall): Promise<ToolResult> {
  const startMs = Date.now();
  
  try {
    console.error(`[tool-executor] Executing ${toolCall.name}`);
    
    let output: unknown;
    
    switch (toolCall.name) {
      case 'ollama_request_draft': {
        output = requestDraft(toolCall.arguments as unknown as RequestDraftInput);
        break;
      }
      
      case 'ollama_write_draft': {
        output = writeDraft(toolCall.arguments as unknown as WriteDraftInput);
        break;
      }
      
      case 'ollama_read_draft': {
        output = readDraft(toolCall.arguments as unknown as ReadDraftInput);
        break;
      }
      
      case 'ollama_submit_draft': {
        output = submitDraft(toolCall.arguments as unknown as SubmitDraftInput);
        break;
      }
      
      default: {
        const durationMs = Date.now() - startMs;
        return {
          success: false,
          output: null,
          error: `Unknown tool: ${toolCall.name}`,
          duration_ms: durationMs,
        };
      }
    }
    
    const durationMs = Date.now() - startMs;
    
    // Check if the output indicates success/failure
    const isSuccessful = typeof output === 'object' && output !== null && 
                        'success' in output && output.success === true;
    
    return {
      success: isSuccessful,
      output,
      duration_ms: durationMs,
    };
    
  } catch (error) {
    const durationMs = Date.now() - startMs;
    const errorMessage = error instanceof Error ? error.message : String(error);
    
    console.error(`[tool-executor] Error executing ${toolCall.name}: ${errorMessage}`);
    
    return {
      success: false,
      output: null,
      error: errorMessage,
      duration_ms: durationMs,
    };
  }
}

/**
 * Execute multiple tool calls in sequence.
 * 
 * @param toolCalls - Array of tool calls to execute
 * @returns Array of tool results
 */
export async function executeTools(toolCalls: ToolCall[]): Promise<ToolResult[]> {
  const results: ToolResult[] = [];
  
  for (const toolCall of toolCalls) {
    const result = await executeTool(toolCall);
    results.push(result);
  }
  
  return results;
}
