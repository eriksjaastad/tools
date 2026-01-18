import { readFileSync, existsSync, writeFileSync } from 'fs';
import { dirname, join } from 'path';
import { DRAFT_REVIEW_TEMPLATE } from '../prompts/draft_review_template';

interface RequestDraftReviewArgs {
  submission_path: string;
}

interface SubmitReviewVerdictArgs {
  submission_path: string;
  verdict: 'ACCEPT' | 'REJECT';
  reason: string;
  reviewer?: string;
}

/**
 * request_draft_review: Prepare a review request for Claude
 * 
 * Returns a formatted prompt that includes submission metadata,
 * original file content, and draft content.
 */
export async function requestDraftReview(args: Record<string, unknown>): Promise<any> {
  const { submission_path } = args as any as RequestDraftReviewArgs;

  if (!existsSync(submission_path)) {
    throw new Error(`Submission not found: ${submission_path}`);
  }

  const submission = JSON.parse(readFileSync(submission_path, 'utf-8'));
  const draftPath = submission.draft_path;
  const originalPath = submission.original_path;

  if (!existsSync(draftPath)) {
    throw new Error(`Draft file not found: ${draftPath}`);
  }

  if (!existsSync(originalPath)) {
    throw new Error(`Original file not found: ${originalPath}`);
  }

  const draftContent = readFileSync(draftPath, 'utf-8');
  const originalContent = readFileSync(originalPath, 'utf-8');

  const prompt = DRAFT_REVIEW_TEMPLATE
    .replace('{{SUBMISSION_JSON}}', JSON.stringify(submission, null, 2))
    .replace('{{ORIGINAL_PATH}}', originalPath)
    .replace('{{DRAFT_PATH}}', draftPath)
    .replace('{{CHANGE_SUMMARY}}', submission.change_summary || 'No summary provided');

  return {
    prompt,
    original_content: originalContent,
    draft_content: draftContent,
    submission_metadata: submission
  };
}

/**
 * submit_review_verdict: Record Claude's verdict
 * 
 * Writes the verdict and reason to a JUDGE_REPORT.json file
 * in the same directory as the submission.
 */
export async function submitReviewVerdict(args: Record<string, unknown>): Promise<any> {
  const { submission_path, verdict, reason, reviewer = 'claude' } = args as any as SubmitReviewVerdictArgs;

  if (!existsSync(submission_path)) {
    throw new Error(`Submission not found: ${submission_path}`);
  }

  const submission = JSON.parse(readFileSync(submission_path, 'utf-8'));
  const reportDir = dirname(submission_path);
  const taskId = submission.task_id || 'unknown_task';

  const report = {
    task_id: taskId,
    timestamp: new Date().toISOString(),
    verdict,
    reason,
    reviewer,
    submission_path
  };

  const reportJsonPath = join(reportDir, `JUDGE_REPORT_${taskId}.json`);
  const reportMdPath = join(reportDir, `JUDGE_REPORT_${taskId}.md`);

  const mdContent = `# Judge Review Report: ${taskId}\n\n` +
    `**Verdict:** ${verdict}\n` +
    `**Reviewer:** ${reviewer}\n` +
    `**Timestamp:** ${report.timestamp}\n\n` +
    `## Reason\n\n${reason}\n`;

  writeFileSync(reportJsonPath, JSON.stringify(report, null, 2));
  writeFileSync(reportMdPath, mdContent);

  return {
    success: true,
    report_json_path: reportJsonPath,
    report_md_path: reportMdPath
  };
}
