/**
 * claude-mcp: MCP server wrapping Claude CLI
 *
 * This server provides constrained tools for Agent Hub.
 * Gemini (Floor Manager) can call these tools but CANNOT send arbitrary prompts.
 *
 * Tools:
 * - claude_judge_review: Code review with structured verdict
 * - claude_validate_proposal: Check proposal completeness
 * - claude_security_audit: Deep security review
 * - claude_resolve_conflict: Resolve Floor Manager vs Judge disputes
 * - claude_health: Check Claude CLI availability
 */

import { createInterface } from 'readline';
import { handleToolCall } from './tools';

// JSON-RPC request/response types
interface JsonRpcRequest {
  jsonrpc: '2.0';
  id: number | string;
  method: string;
  params?: {
    name: string;
    arguments: Record<string, unknown>;
  };
}

interface JsonRpcResponse {
  jsonrpc: '2.0';
  id: number | string;
  result?: unknown;
  error?: {
    code: number;
    message: string;
  };
}

// MCP server main loop
async function main() {
  const rl = createInterface({
    input: process.stdin,
    output: process.stdout,
    terminal: false
  });

  rl.on('line', async (line) => {
    try {
      const request: JsonRpcRequest = JSON.parse(line);

      if (request.method === 'tools/call' && request.params) {
        const { name, arguments: args } = request.params;

        try {
          const result = await handleToolCall(name, args);
          const response: JsonRpcResponse = {
            jsonrpc: '2.0',
            id: request.id,
            result
          };
          console.log(JSON.stringify(response));
        } catch (err) {
          const response: JsonRpcResponse = {
            jsonrpc: '2.0',
            id: request.id,
            error: {
              code: -32000,
              message: err instanceof Error ? err.message : 'Unknown error'
            }
          };
          console.log(JSON.stringify(response));
        }
      } else if (request.method === 'tools/list') {
        // Return available tools
        const response: JsonRpcResponse = {
          jsonrpc: '2.0',
          id: request.id,
          result: {
            tools: [
              { name: 'claude_judge_review', description: 'Code review with structured verdict' },
              { name: 'request_draft_review', description: 'Request Claude to review a draft' },
              { name: 'submit_review_verdict', description: 'Record Claude review verdict' },
              { name: 'claude_validate_proposal', description: 'Check proposal completeness' },
              { name: 'claude_security_audit', description: 'Deep security review' },
              { name: 'claude_resolve_conflict', description: 'Resolve disputes' },
              { name: 'claude_health', description: 'Check CLI availability' },
              { name: 'hub_connect', description: 'Register agent with the hub' },
              { name: 'hub_send_message', description: 'Send message to another agent' },
              { name: 'hub_receive_messages', description: 'Check inbox for pending messages' },
              { name: 'hub_heartbeat', description: 'Signal agent is alive' },
              { name: 'hub_send_answer', description: 'Answer a previous question' },
              { name: 'hub_get_all_messages', description: 'Get all messages (debug)' }
            ]
          }
        };
        console.log(JSON.stringify(response));
      }
    } catch (err) {
      // Invalid JSON - ignore
    }
  });
}

main().catch(console.error);
