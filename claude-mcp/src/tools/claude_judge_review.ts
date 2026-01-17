/**
 * claude_judge_review: The Judge role - architectural code review
 *
 * Gemini provides: contract_path
 * Claude sees: Fixed Judge prompt template with contract injected
 *
 * This is the main review tool for Agent Hub.
 */

import { spawn } from 'child_process';
import { readFileSync, existsSync } from 'fs';
import { JUDGE_PROMPT_TEMPLATE } from '../prompts/judge_template';

interface JudgeReviewArgs {
  contract_path: string;
  report_dir?: string;
  timeout_seconds?: number;
}

interface JudgeReviewResult {
  success: boolean;
  verdict?: 'PASS' | 'CONDITIONAL' | 'FAIL' | 'CRITICAL_HALT';
  blocking_issues_count?: number;
  report_md_path?: string;
  report_json_path?: string;
  error?: string;
  duration_ms: number;
  timed_out: boolean;
}

export async function claudeJudgeReview(args: Record<string, unknown>): Promise<JudgeReviewResult> {
  const startTime = Date.now();
  const {
    contract_path,
    report_dir = '_handoff',
    timeout_seconds = 900
  } = args as any as JudgeReviewArgs;

  // Validate contract exists
  if (!existsSync(contract_path)) {
    return {
      success: false,
      error: `Contract not found: ${contract_path}`,
      duration_ms: Date.now() - startTime,
      timed_out: false
    };
  }

  // Read contract
  let contract: Record<string, unknown>;
  try {
    contract = JSON.parse(readFileSync(contract_path, 'utf-8'));
  } catch (err) {
    return {
      success: false,
      error: `Failed to parse contract: ${err}`,
      duration_ms: Date.now() - startTime,
      timed_out: false
    };
  }

  // Build the prompt from template (Gemini never sees this)
  const prompt = JUDGE_PROMPT_TEMPLATE
    .replace('{{CONTRACT_JSON}}', JSON.stringify(contract, null, 2))
    .replace('{{REPORT_DIR}}', report_dir);

  // Invoke Claude CLI
  return new Promise((resolve) => {
    let timedOut = false;

    const proc = spawn('claude', ['--dangerously-skip-permissions'], {
      cwd: process.cwd(),
      stdio: ['pipe', 'pipe', 'pipe']
    });

    const timeoutId = setTimeout(() => {
      timedOut = true;
      proc.kill('SIGTERM');
    }, timeout_seconds * 1000);

    let stdout = '';
    let stderr = '';

    proc.stdout.on('data', (data) => {
      stdout += data.toString();
    });

    proc.stderr.on('data', (data) => {
      stderr += data.toString();
    });

    // Send prompt to stdin
    proc.stdin.write(prompt);
    proc.stdin.end();

    proc.on('close', (code) => {
      clearTimeout(timeoutId);

      if (timedOut) {
        resolve({
          success: false,
          error: 'Claude timed out',
          duration_ms: Date.now() - startTime,
          timed_out: true
        });
        return;
      }

      // Check if reports were created
      const reportMdPath = `${report_dir}/JUDGE_REPORT.md`;
      const reportJsonPath = `${report_dir}/JUDGE_REPORT.json`;

      if (existsSync(reportJsonPath)) {
        try {
          const report = JSON.parse(readFileSync(reportJsonPath, 'utf-8'));
          resolve({
            success: true,
            verdict: report.verdict,
            blocking_issues_count: report.blocking_issues?.length || 0,
            report_md_path: reportMdPath,
            report_json_path: reportJsonPath,
            duration_ms: Date.now() - startTime,
            timed_out: false
          });
        } catch {
          resolve({
            success: true,
            report_md_path: reportMdPath,
            report_json_path: reportJsonPath,
            duration_ms: Date.now() - startTime,
            timed_out: false
          });
        }
      } else {
        resolve({
          success: false,
          error: stderr || 'No report generated',
          duration_ms: Date.now() - startTime,
          timed_out: false
        });
      }
    });

    proc.on('error', (err) => {
      clearTimeout(timeoutId);
      resolve({
        success: false,
        error: `Failed to spawn Claude: ${err.message}`,
        duration_ms: Date.now() - startTime,
        timed_out: false
      });
    });
  });
}
