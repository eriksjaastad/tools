/**
 * Draft tools for Sandbox Draft Pattern (V4).
 * These tools allow local models to edit files in a controlled sandbox.
 */

import * as fs from 'fs';
import * as path from 'path';
import { fileURLToPath } from 'url';
import {
    RequestDraftInput,
    RequestDraftResult,
    WriteDraftInput,
    WriteDraftResult,
    ReadDraftInput,
    ReadDraftResult,
    SubmitDraftInput,
    SubmitDraftResult,
} from './draft-types.js';
import {
    validateSandboxWrite,
    validateSourceRead,
    getDraftPath,
    getSubmissionPath,
    computeFileHash,
    computeContentHash,
    ensureSandboxExists,
} from './sandbox-utils.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Default workspace root - points to the projects directory
const DEFAULT_WORKSPACE = path.resolve(__dirname, '../../../');

/**
 * Request a draft copy of a file for editing.
 */
export function requestDraft(input: RequestDraftInput): RequestDraftResult {
    try {
        const { source_path, task_id } = input;

        // Validate source can be read
        const readValidation = validateSourceRead(source_path, DEFAULT_WORKSPACE);
        if (!readValidation.valid) {
            return {
                success: false,
                error: readValidation.reason
            };
        }

        // Ensure sandbox exists
        ensureSandboxExists();

        // Generate draft path
        const draftPath = getDraftPath(source_path, task_id);

        // Validate draft path (should always pass, but defense in depth)
        const writeValidation = validateSandboxWrite(draftPath);
        if (!writeValidation.valid) {
            return {
                success: false,
                error: writeValidation.reason
            };
        }

        // Copy source to draft (atomic write with tmp+rename)
        const sourceContent = fs.readFileSync(readValidation.resolvedPath!, 'utf-8');
        const tmpPath = `${draftPath}.tmp`;
        fs.writeFileSync(tmpPath, sourceContent, 'utf-8');
        fs.renameSync(tmpPath, draftPath);

        // Compute hash and line count
        const originalHash = computeFileHash(readValidation.resolvedPath!);
        const lineCount = sourceContent.split('\n').length;

        console.error(`Draft created: ${draftPath}`);

        return {
            success: true,
            draft_path: draftPath,
            original_hash: originalHash,
            line_count: lineCount
        };
    } catch (error) {
        return {
            success: false,
            error: `Failed to create draft: ${error}`
        };
    }
}

/**
 * Write content to a draft file (sandbox only).
 */
export function writeDraft(input: WriteDraftInput): WriteDraftResult {
    try {
        const { draft_path, content } = input;

        // CRITICAL: Validate path is in sandbox
        const validation = validateSandboxWrite(draft_path);
        if (!validation.valid) {
            console.error(`SECURITY: Attempted write outside sandbox: ${draft_path}`);
            return {
                success: false,
                error: validation.reason
            };
        }

        // Write atomically (tmp + rename)
        const tmpPath = `${validation.resolvedPath}.tmp`;
        fs.writeFileSync(tmpPath, content, 'utf-8');
        fs.renameSync(tmpPath, validation.resolvedPath!);

        // Compute new hash and line count
        const newHash = computeContentHash(content);
        const lineCount = content.split('\n').length;

        console.error(`Draft updated: ${draft_path}`);

        return {
            success: true,
            new_hash: newHash,
            line_count: lineCount
        };
    } catch (error) {
        return {
            success: false,
            error: `Failed to write draft: ${error}`
        };
    }
}

/**
 * Read current draft content.
 */
export function readDraft(input: ReadDraftInput): ReadDraftResult {
    try {
        const { draft_path } = input;

        // Validate path is in sandbox (even for reads, enforce sandbox)
        const validation = validateSandboxWrite(draft_path);
        if (!validation.valid) {
            return {
                success: false,
                error: validation.reason
            };
        }

        // Check file exists
        if (!fs.existsSync(validation.resolvedPath!)) {
            return {
                success: false,
                error: `Draft not found: ${draft_path}`
            };
        }

        // Read content
        const content = fs.readFileSync(validation.resolvedPath!, 'utf-8');
        const lineCount = content.split('\n').length;

        return {
            success: true,
            content: content,
            line_count: lineCount
        };
    } catch (error) {
        return {
            success: false,
            error: `Failed to read draft: ${error}`
        };
    }
}

/**
 * Submit draft for Floor Manager review.
 */
export function submitDraft(input: SubmitDraftInput): SubmitDraftResult {
    try {
        const { draft_path, original_path, task_id, change_summary } = input;

        // Validate draft path
        const draftValidation = validateSandboxWrite(draft_path);
        if (!draftValidation.valid) {
            return {
                success: false,
                error: draftValidation.reason
            };
        }

        // Check draft exists
        if (!fs.existsSync(draftValidation.resolvedPath!)) {
            return {
                success: false,
                error: `Draft not found: ${draft_path}`
            };
        }

        // Validate original path exists
        const originalValidation = validateSourceRead(original_path, DEFAULT_WORKSPACE);
        if (!originalValidation.valid) {
            return {
                success: false,
                error: `Original file issue: ${originalValidation.reason}`
            };
        }

        // Read both files for diff preview
        const originalContent = fs.readFileSync(originalValidation.resolvedPath!, 'utf-8');
        const draftContent = fs.readFileSync(draftValidation.resolvedPath!, 'utf-8');

        // Generate simple diff preview (line count changes)
        const originalLines = originalContent.split('\n').length;
        const draftLines = draftContent.split('\n').length;
        const diffPreview = `Original: ${originalLines} lines, Draft: ${draftLines} lines (${draftLines - originalLines >= 0 ? '+' : ''}${draftLines - originalLines})`;

        // Create submission metadata
        const submissionPath = getSubmissionPath(task_id);
        const submission = {
            task_id,
            draft_path: draftValidation.resolvedPath,
            original_path: originalValidation.resolvedPath,
            change_summary,
            submitted_at: new Date().toISOString(),
            original_hash: computeFileHash(originalValidation.resolvedPath!),
            draft_hash: computeFileHash(draftValidation.resolvedPath!),
            original_lines: originalLines,
            draft_lines: draftLines,
        };

        fs.writeFileSync(submissionPath, JSON.stringify(submission, null, 2), 'utf-8');

        console.error(`Draft submitted: ${submissionPath}`);

        return {
            success: true,
            submission_path: submissionPath,
            diff_preview: diffPreview
        };
    } catch (error) {
        return {
            success: false,
            error: `Failed to submit draft: ${error}`
        };
    }
}
