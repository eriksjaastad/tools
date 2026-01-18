/**
 * Tool Call Parser for Agent Loop Dispatcher.
 * Extracts tool calls from model text output.
 */

import { ToolCall } from './agent-types.js';

// Whitelist of valid tools that can be called
const VALID_TOOLS = [
  'ollama_request_draft',
  'ollama_write_draft',
  'ollama_read_draft',
  'ollama_submit_draft',
];

/**
 * Parse tool calls from model output.
 * Supports both JSON and XML-style formats.
 * 
 * @param output - Raw model output text
 * @returns Array of parsed tool calls (empty if none found)
 */
export function parseToolCalls(output: string): ToolCall[] {
  const toolCalls: ToolCall[] = [];

  // Strategy 1: Look for JSON blocks
  const jsonToolCalls = parseJsonToolCalls(output);
  toolCalls.push(...jsonToolCalls);

  // Strategy 2: Look for XML-style tool calls
  const xmlToolCalls = parseXmlToolCalls(output);
  toolCalls.push(...xmlToolCalls);

  // Filter to only valid tools
  const validatedCalls = toolCalls.filter(call => {
    if (!VALID_TOOLS.includes(call.name)) {
      console.warn(`[tool-call-parser] Ignoring invalid tool: ${call.name}`);
      return false;
    }
    return true;
  });

  return validatedCalls;
}

/**
 * Extract complete JSON blocks from text (handles multi-line JSON).
 */
function extractJsonBlocks(output: string): string[] {
  const blocks: string[] = [];
  let depth = 0;
  let start = -1;

  for (let i = 0; i < output.length; i++) {
    if (output[i] === '{') {
      if (depth === 0) start = i;
      depth++;
    } else if (output[i] === '}') {
      depth--;
      if (depth === 0 && start !== -1) {
        blocks.push(output.slice(start, i + 1));
        start = -1;
      }
    }
  }

  return blocks;
}

/**
 * Parse JSON-style tool calls from output.
 * Example: {"name": "tool", "arguments": {...}}
 * Handles both single-line and multi-line JSON.
 */
function parseJsonToolCalls(output: string): ToolCall[] {
  const toolCalls: ToolCall[] = [];
  
  // Extract complete JSON blocks (handles multi-line)
  const jsonBlocks = extractJsonBlocks(output);
  
  for (const block of jsonBlocks) {
    try {
      const parsed = JSON.parse(block);
      
      // Check if it looks like a tool call
      if (parsed.name && typeof parsed.name === 'string' && 
          parsed.arguments && typeof parsed.arguments === 'object') {
        toolCalls.push({
          name: parsed.name,
          arguments: parsed.arguments as Record<string, unknown>,
          thought: parsed.thought,
        });
      }
    } catch (error) {
      // Not valid JSON, continue
      continue;
    }
  }
  
  return toolCalls;
}

/**
 * Parse XML-style tool calls from output.
 * Example: <tool_call><name>tool</name><arguments>{...}</arguments></tool_call>
 */
function parseXmlToolCalls(output: string): ToolCall[] {
  const toolCalls: ToolCall[] = [];
  
  // Regex to match XML-style tool calls
  const toolCallRegex = /<tool_call>([\s\S]*?)<\/tool_call>/g;
  const matches = output.matchAll(toolCallRegex);
  
  for (const match of matches) {
    const content = match[1];
    
    try {
      // Extract name
      const nameMatch = content.match(/<name>(.*?)<\/name>/);
      const name = nameMatch ? nameMatch[1].trim() : null;
      
      // Extract arguments
      const argsMatch = content.match(/<arguments>([\s\S]*?)<\/arguments>/);
      const argsJson = argsMatch ? argsMatch[1].trim() : null;
      
      if (name && argsJson) {
        const args = JSON.parse(argsJson);
        toolCalls.push({
          name,
          arguments: args as Record<string, unknown>,
        });
      }
    } catch (error) {
      console.warn(`[tool-call-parser] Failed to parse XML tool call: ${error}`);
      continue;
    }
  }
  
  return toolCalls;
}
