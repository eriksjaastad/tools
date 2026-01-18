/**
 * Tool dispatcher - routes tool calls to implementations
 *
 * IMPORTANT: This is the guardrail. Only predefined tools are allowed.
 * No arbitrary prompts can be sent to Claude through this server.
 */

import { claudeJudgeReview } from './claude_judge_review';
import { requestDraftReview, submitReviewVerdict } from './draft_review';
import { claudeValidateProposal } from './claude_validate_proposal';
import { claudeSecurityAudit } from './claude_security_audit';
import { claudeResolveConflict } from './claude_resolve_conflict';
import { claudeHealth } from './claude_health';
import {
  hubConnect,
  hubSendMessage,
  hubReceiveMessages,
  hubHeartbeat,
  hubSendAnswer,
  hubGetAllMessages
} from './hub';

// The allowed tools - this is the "menu"
const TOOLS: Record<string, (args: Record<string, unknown>) => Promise<unknown>> = {
  'claude_judge_review': claudeJudgeReview,
  'request_draft_review': requestDraftReview,
  'submit_review_verdict': submitReviewVerdict,
  'claude_validate_proposal': claudeValidateProposal,
  'claude_security_audit': claudeSecurityAudit,
  'claude_resolve_conflict': claudeResolveConflict,
  'claude_health': claudeHealth,
  'hub_connect': hubConnect,
  'hub_send_message': hubSendMessage,
  'hub_receive_messages': hubReceiveMessages,
  'hub_heartbeat': hubHeartbeat,
  'hub_send_answer': hubSendAnswer,
  'hub_get_all_messages': hubGetAllMessages,
};

export async function handleToolCall(
  name: string,
  args: Record<string, unknown>
): Promise<unknown> {
  const tool = TOOLS[name];

  if (!tool) {
    throw new Error(`Unknown tool: ${name}. Available tools: ${Object.keys(TOOLS).join(', ')}`);
  }

  return tool(args);
}
