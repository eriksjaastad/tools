/**
 * Sandbox path validation utilities.
 * SECURITY CRITICAL: These functions gate all draft file operations.
 */

import * as path from 'path';
import * as fs from 'fs';
import * as crypto from 'crypto';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// The sandbox directory - ONLY place workers can write
// This should point to agent-hub's _handoff/drafts
const SANDBOX_DIR = path.resolve(__dirname, '../../agent-hub/_handoff/drafts');

// Sensitive file patterns that cannot be drafted
const SENSITIVE_PATTERNS = ['.env', 'credentials', 'secret', '.key', '.pem', 'password'];

export interface ValidationResult {
    valid: boolean;
    reason: string;
    resolvedPath?: string;
}

/**
 * Validate that a path is safe for writing (must be in sandbox).
 */
export function validateSandboxWrite(targetPath: string): ValidationResult {
    try {
        const resolved = path.resolve(targetPath);
        const sandboxResolved = path.resolve(SANDBOX_DIR);

        // Check 1: Must be inside sandbox
        if (!resolved.startsWith(sandboxResolved + path.sep) && resolved !== sandboxResolved) {
            console.warn(`SECURITY: Write blocked - outside sandbox: ${resolved}`);
            return {
                valid: false,
                reason: `Path outside sandbox: ${resolved}`
            };
        }

        // Check 2: No path traversal
        if (targetPath.includes('..')) {
            console.warn(`SECURITY: Write blocked - path traversal: ${targetPath}`);
            return {
                valid: false,
                reason: 'Path traversal not allowed'
            };
        }

        // Check 3: Valid extension
        const ext = path.extname(resolved);
        const validExtensions = ['.draft', '.json'];
        if (!validExtensions.includes(ext)) {
            // Special case for .submission.json
            if (!resolved.endsWith('.submission.json')) {
                console.warn(`SECURITY: Write blocked - invalid extension: ${ext}`);
                return {
                    valid: false,
                    reason: `Invalid extension: ${ext}`
                };
            }
        }

        return {
            valid: true,
            reason: 'OK',
            resolvedPath: resolved
        };
    } catch (error) {
        return {
            valid: false,
            reason: `Validation error: ${error}`
        };
    }
}

/**
 * Validate that a source file can be read for drafting.
 */
export function validateSourceRead(sourcePath: string, workspaceRoot: string): ValidationResult {
    try {
        const resolved = path.resolve(sourcePath);
        const workspaceResolved = path.resolve(workspaceRoot);

        // Check 1: Must be inside workspace
        if (!resolved.startsWith(workspaceResolved + path.sep) && resolved !== workspaceResolved) {
            console.warn(`SECURITY: Read blocked - outside workspace: ${resolved}`);
            return {
                valid: false,
                reason: `Path outside workspace: ${resolved}`
            };
        }

        // Check 2: File must exist
        if (!fs.existsSync(resolved)) {
            return {
                valid: false,
                reason: `File not found: ${resolved}`
            };
        }

        // Check 3: Must be a file
        const stats = fs.statSync(resolved);
        if (!stats.isFile()) {
            return {
                valid: false,
                reason: `Not a file: ${resolved}`
            };
        }

        // Check 4: Block sensitive files
        const filename = path.basename(resolved).toLowerCase();
        for (const pattern of SENSITIVE_PATTERNS) {
            if (filename.includes(pattern)) {
                console.warn(`SECURITY: Read blocked - sensitive file: ${resolved}`);
                return {
                    valid: false,
                    reason: `Cannot draft sensitive files: ${filename}`
                };
            }
        }

        return {
            valid: true,
            reason: 'OK',
            resolvedPath: resolved
        };
    } catch (error) {
        return {
            valid: false,
            reason: `Validation error: ${error}`
        };
    }
}

/**
 * Generate draft path for a source file.
 */
export function getDraftPath(sourcePath: string, taskId: string): string {
    // Sanitize task ID
    const safeTaskId = taskId.replace(/[^a-zA-Z0-9_]/g, '_');
    const basename = path.basename(sourcePath);
    return path.join(SANDBOX_DIR, `${basename}.${safeTaskId}.draft`);
}

/**
 * Generate submission metadata path.
 */
export function getSubmissionPath(taskId: string): string {
    const safeTaskId = taskId.replace(/[^a-zA-Z0-9_]/g, '_');
    return path.join(SANDBOX_DIR, `${safeTaskId}.submission.json`);
}

/**
 * Compute SHA256 hash of file content.
 */
export function computeFileHash(filePath: string): string {
    const content = fs.readFileSync(filePath);
    return crypto.createHash('sha256').update(content).digest('hex');
}

/**
 * Compute SHA256 hash of string content.
 */
export function computeContentHash(content: string): string {
    return crypto.createHash('sha256').update(content).digest('hex');
}

/**
 * Ensure sandbox directory exists.
 */
export function ensureSandboxExists(): void {
    if (!fs.existsSync(SANDBOX_DIR)) {
        fs.mkdirSync(SANDBOX_DIR, { recursive: true });
    }
}

/**
 * Get the sandbox directory path.
 */
export function getSandboxDir(): string {
    return SANDBOX_DIR;
}
