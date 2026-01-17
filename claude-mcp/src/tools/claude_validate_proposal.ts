/**
 * claude_validate_proposal: Check if a proposal is complete and actionable
 *
 * Used before Floor Manager converts PROPOSAL_FINAL.md to contract.
 */

import { spawn } from 'child_process';
import { readFileSync, existsSync } from 'fs';

interface ValidateProposalArgs {
  proposal_path: string;
  timeout_seconds?: number;
}

interface ValidateProposalResult {
  success: boolean;
  valid?: boolean;
  issues?: string[];
  error?: string;
  duration_ms: number;
}

const VALIDATE_PROMPT_TEMPLATE = `
You are validating a proposal for the Agent Hub pipeline.

## Proposal Content

\`\`\`markdown
{{PROPOSAL_CONTENT}}
\`\`\`

## Validation Checklist

Check if the proposal has:
1. Clear title
2. Target project specified
3. Complexity level (trivial/minor/major/critical)
4. Source files listed
5. Target output file specified
6. At least one requirement
7. At least one acceptance criterion
8. Constraints defined (allowed paths, forbidden paths)

## Required Output

Respond with ONLY this JSON (no other text):

{
  "valid": true/false,
  "issues": ["list of missing or unclear items"]
}
`;

export async function claudeValidateProposal(args: Record<string, unknown>): Promise<ValidateProposalResult> {
  const startTime = Date.now();
  const {
    proposal_path,
    timeout_seconds = 120
  } = args as ValidateProposalArgs;

  if (!existsSync(proposal_path)) {
    return {
      success: false,
      error: `Proposal not found: ${proposal_path}`,
      duration_ms: Date.now() - startTime
    };
  }

  const proposalContent = readFileSync(proposal_path, 'utf-8');
  const prompt = VALIDATE_PROMPT_TEMPLATE.replace('{{PROPOSAL_CONTENT}}', proposalContent);

  return new Promise((resolve) => {
    const proc = spawn('claude', ['--dangerously-skip-permissions', '--print'], {
      stdio: ['pipe', 'pipe', 'pipe']
    });

    const timeoutId = setTimeout(() => {
      proc.kill('SIGTERM');
      resolve({
        success: false,
        error: 'Validation timed out',
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
        // Extract JSON from response
        const jsonMatch = stdout.match(/\{[\s\S]*\}/);
        if (jsonMatch) {
          const result = JSON.parse(jsonMatch[0]);
          resolve({
            success: true,
            valid: result.valid,
            issues: result.issues || [],
            duration_ms: Date.now() - startTime
          });
        } else {
          resolve({
            success: false,
            error: 'Could not parse validation response',
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
