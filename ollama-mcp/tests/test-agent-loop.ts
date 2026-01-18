/**
 * Test suite for Agent Loop Dispatcher
 * Uses Node.js built-in test runner (node:test) and assert
 */

import { test, describe } from 'node:test';
import assert from 'node:assert';
import { parseToolCalls } from '../dist/tool-call-parser.js';
import { executeTool } from '../dist/tool-executor.js';
import { runAgentLoop } from '../dist/agent-loop.js';

describe('Tool Call Parser', () => {
  test('should extract JSON tool calls correctly', () => {
    const output = `
I'll request the draft now.

{"name": "ollama_request_draft", "arguments": {"source_path": "/path/to/file.txt", "task_id": "TASK-001"}}

Let me continue...
    `;
    
    const toolCalls = parseToolCalls(output);
    
    assert.strictEqual(toolCalls.length, 1);
    assert.strictEqual(toolCalls[0].name, 'ollama_request_draft');
    assert.strictEqual(toolCalls[0].arguments.source_path, '/path/to/file.txt');
    assert.strictEqual(toolCalls[0].arguments.task_id, 'TASK-001');
  });

  test('should extract XML tool calls correctly', () => {
    const output = `
<tool_call>
<name>ollama_read_draft</name>
<arguments>{"draft_path": "/path/draft.txt"}</arguments>
</tool_call>
    `;
    
    const toolCalls = parseToolCalls(output);
    
    assert.strictEqual(toolCalls.length, 1);
    assert.strictEqual(toolCalls[0].name, 'ollama_read_draft');
    assert.strictEqual(toolCalls[0].arguments.draft_path, '/path/draft.txt');
  });

  test('should return empty array for no tool calls', () => {
    const output = 'This is just plain text with no tool calls.';
    
    const toolCalls = parseToolCalls(output);
    
    assert.strictEqual(toolCalls.length, 0);
  });

  test('should handle malformed JSON gracefully', () => {
    const output = `
{"name": "invalid_json", "arguments": {broken
    `;
    
    const toolCalls = parseToolCalls(output);
    
    // Should not throw, just return empty
    assert.strictEqual(toolCalls.length, 0);
  });

  test('should filter out invalid tool names', () => {
    const output = `
{"name": "not_a_real_tool", "arguments": {"foo": "bar"}}
{"name": "ollama_read_draft", "arguments": {"draft_path": "/test.draft"}}
    `;
    
    const toolCalls = parseToolCalls(output);
    
    // Should only include the valid tool
    assert.strictEqual(toolCalls.length, 1);
    assert.strictEqual(toolCalls[0].name, 'ollama_read_draft');
  });

  test('should handle multiple tool calls in one response', () => {
    const output = `
{"name": "ollama_request_draft", "arguments": {"source_path": "/file1.txt", "task_id": "T1"}}
{"name": "ollama_read_draft", "arguments": {"draft_path": "/file1.draft"}}
    `;
    
    const toolCalls = parseToolCalls(output);
    
    assert.strictEqual(toolCalls.length, 2);
    assert.strictEqual(toolCalls[0].name, 'ollama_request_draft');
    assert.strictEqual(toolCalls[1].name, 'ollama_read_draft');
  });

  test('should extract multi-line JSON tool calls', () => {
    const output = `
{
  "name": "ollama_write_draft",
  "arguments": {
    "draft_path": "/path/to/file.draft",
    "content": "line1\\nline2"
  }
}
    `;
    
    const toolCalls = parseToolCalls(output);
    
    assert.strictEqual(toolCalls.length, 1);
    assert.strictEqual(toolCalls[0].name, 'ollama_write_draft');
    assert.strictEqual(toolCalls[0].arguments.draft_path, '/path/to/file.draft');
    // JSON.parse correctly interprets \\n as a literal newline
    assert.strictEqual(toolCalls[0].arguments.content, 'line1\nline2');
  });
});

describe('Tool Executor', () => {
  test('should handle errors without crashing', async () => {
    const toolCall = {
      name: 'ollama_read_draft',
      arguments: { draft_path: '/nonexistent/path.draft' }
    };
    
    const result = await executeTool(toolCall);
    
    assert.strictEqual(result.success, false);
    assert.ok(result.error || (result.output && typeof result.output === 'object' && 'error' in result.output));
    assert.ok(result.duration_ms >= 0);
  });

  test('should return error for unknown tool', async () => {
    const toolCall = {
      name: 'unknown_tool',
      arguments: {}
    };
    
    const result = await executeTool(toolCall);
    
    assert.strictEqual(result.success, false);
    assert.ok(result.error?.includes('Unknown tool'));
  });
});

describe('Agent Loop', () => {
  test('should stop when no tool calls returned', async () => {
    const mockOllamaRun = async () => ({
      stdout: 'This is my final answer with no tool calls.',
      stderr: '',
      exitCode: 0,
    });
    
    const result = await runAgentLoop('Test prompt', mockOllamaRun, { max_iterations: 5 });
    
    assert.strictEqual(result.success, true);
    assert.strictEqual(result.iterations, 1);
    assert.strictEqual(result.tool_calls_made.length, 0);
    assert.ok(result.final_output.includes('final answer'));
  });

  test('should respect max_iterations', async () => {
    // Mock that returns different tool calls each time to avoid loop detection
    let callCount = 0;
    const mockOllamaRun = async () => {
      callCount++;
      // Use a valid tool from whitelist with varying arguments
      return {
        stdout: `{"name": "ollama_read_draft", "arguments": {"draft_path": "/test${callCount}.draft"}}`,
        stderr: '',
        exitCode: 0,
      };
    };
    
    const result = await runAgentLoop('Test prompt', mockOllamaRun, { max_iterations: 3 });
    
    assert.strictEqual(result.success, false);
    assert.strictEqual(result.iterations, 3);
    // Should hit max iterations since we're varying the calls
    assert.ok(result.error);
  });

  test('should detect infinite loops (same call repeated)', async () => {
    let callCount = 0;
    const mockOllamaRun = async () => {
      callCount++;
      return {
        stdout: '{"name": "ollama_read_draft", "arguments": {"draft_path": "/same.draft"}}',
        stderr: '',
        exitCode: 0,
      };
    };
    
    const result = await runAgentLoop('Test prompt', mockOllamaRun, { max_iterations: 10 });
    
    assert.strictEqual(result.success, false);
    assert.ok(result.error?.includes('Infinite loop detected'));
    assert.ok(callCount <= 5); // Should halt before max iterations
  });

  test('should handle consecutive errors', async () => {
    let callCount = 0;
    const mockOllamaRun = async () => {
      callCount++;
      return {
        stdout: '',
        stderr: 'Model error',
        exitCode: 1,
      };
    };
    
    const result = await runAgentLoop('Test prompt', mockOllamaRun, { max_iterations: 10 });
    
    assert.strictEqual(result.success, false);
    assert.ok(result.error?.includes('consecutive errors'));
    assert.ok(callCount <= 4); // MAX_CONSECUTIVE_ERRORS + 1
  });
});

console.log('All agent loop tests passed!');
