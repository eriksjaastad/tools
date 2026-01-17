/**
 * claude_resolve_conflict: Decide who's right when Floor Manager and Judge disagree
 *
 * Used in rebuttal situations to get a fresh perspective.
 */

import { spawn } from 'child_process';
import { readFileSync, existsSync } from 'fs';

interface ResolveConflictArgs {
  contract_path: string;
  rebuttal_path: string;
  judge_report_path: string;
  timeout_seconds?: number;
}

interface ResolveConflictResult {
  success: boolean;
  side?: 'floor_manager' | 'judge';
  reasoning?: string;
  recommendation?: string;
  error?: string;
  duration_ms: number;
}

const RESOLVE_CONFLICT_TEMPLATE = `
You are resolving a disagreement between the Floor Manager and the Judge in the Agent Hub pipeline.

## Task Contract

\`\`\`json
{{CONTRACT_JSON}}
\`\`\`

## Judge's Report

\`\`\`markdown
{{JUDGE_REPORT}}
\`\`\`

## Floor Manager's Rebuttal

\`\`\`markdown
{{REBUTTAL}}
\`\`\`

## Your Task

1. Read both positions carefully
2. Consider the original requirements and acceptance criteria
3. Determine who is correct
4. Provide a clear recommendation

## Required Output

Respond with ONLY this JSON (no other text):

{
  "side": "floor_manager" or "judge",
  "reasoning": "Why this side is correct",
  "recommendation": "What action to take next"
}
`;

export async function claudeResolveConflict(args: Record<string, unknown>): Promise<ResolveConflictResult> {
  const startTime = Date.now();
  const {
    contract_path,
    rebuttal_path,
    judge_report_path,
    timeout_seconds = 300
  } = args as ResolveConflictArgs;

  // Read all files
  const files = { contract_path, rebuttal_path, judge_report_path };
  for (const [name, path] of Object.entries(files)) {
    if (!existsSync(path)) {
      return {
        success: false,
        error: `${name} not found: ${path}`,
        duration_ms: Date.now() - startTime
      };
    }
  }

  const contract = readFileSync(contract_path, 'utf-8');
  const judgeReport = readFileSync(judge_report_path, 'utf-8');
  const rebuttal = readFileSync(rebuttal_path, 'utf-8');

  const prompt = RESOLVE_CONFLICT_TEMPLATE
    .replace('{{CONTRACT_JSON}}', contract)
    .replace('{{JUDGE_REPORT}}', judgeReport)
    .replace('{{REBUTTAL}}', rebuttal);

  return new Promise((resolve) => {
    const proc = spawn('claude', ['--dangerously-skip-permissions', '--print'], {
      stdio: ['pipe', 'pipe', 'pipe']
    });

    const timeoutId = setTimeout(() => {
      proc.kill('SIGTERM');
      resolve({
        success: false,
        error: 'Conflict resolution timed out',
        duration_ms: Date.now() - startTime
      });
    }, timeout_seconds * 1000);

    let stdout = '';

    proc.stdout.on('data', (data) => {
      stdout += data.toString();
    });

    proc.stdin.write(prompt);
    proc.stdin.end();

    proc.on('close', () => {
      clearTimeout(timeoutId);

      try {
        const jsonMatch = stdout.match(/\{[\s\S]*\}/);
        if (jsonMatch) {
          const result = JSON.parse(jsonMatch[0]);
          resolve({
            success: true,
            side: result.side,
            reasoning: result.reasoning,
            recommendation: result.recommendation,
            duration_ms: Date.now() - startTime
          });
        } else {
          resolve({
            success: false,
            error: 'Could not parse resolution response',
            duration_ms: Date.now() - startTime
          });
        }
      } catch (err) {
        resolve({
          success: false,
          error: `Parse error: ${err}`,
          duration_ms: Date.now() - startTime
        });
      }
    });
  });
}
