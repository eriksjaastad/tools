# Phase 12: Ollama MCP Draft Tools

**Goal:** Add four new tools to `ollama-mcp` that allow local models to work with sandbox drafts.

**Prerequisites:** Phase 11 complete (sandbox infrastructure exists).

**Important:** This phase modifies `ollama-mcp`, NOT `agent-hub`. The Floor Manager needs to work in `/Users/eriksjaastad/projects/_tools/ollama-mcp/`.

---

## The Four Tools

| Tool | Purpose |
|------|---------|
| `ollama_request_draft` | Copy a source file to the sandbox for editing |
| `ollama_write_draft` | Write content to a draft file (sandbox only) |
| `ollama_read_draft` | Read current draft content |
| `ollama_submit_draft` | Signal draft is ready for Floor Manager review |

---

## Prompt 12.1: Add Draft Types

### Context
We need TypeScript types for the draft tools. These go in the existing types or a new types file.

### Task
Create `src/draft-types.ts`:

```typescript
/**
 * Types for Sandbox Draft Pattern (V4).
 * These tools allow local models to edit files in a controlled sandbox.
 */

export interface RequestDraftInput {
  source_path: string;
  task_id: string;
}

export interface RequestDraftResult {
  success: boolean;
  draft_path?: string;
  original_hash?: string;
  line_count?: number;
  error?: string;
}

export interface WriteDraftInput {
  draft_path: string;
  content: string;
}

export interface WriteDraftResult {
  success: boolean;
  new_hash?: string;
  line_count?: number;
  error?: string;
}

export interface ReadDraftInput {
  draft_path: string;
}

export interface ReadDraftResult {
  success: boolean;
  content?: string;
  line_count?: number;
  error?: string;
}

export interface SubmitDraftInput {
  draft_path: string;
  original_path: string;
  task_id: string;
  change_summary: string;
}

export interface SubmitDraftResult {
  success: boolean;
  submission_path?: string;
  diff_preview?: string;
  error?: string;
}
```

### File Location
`/Users/eriksjaastad/projects/_tools/ollama-mcp/src/draft-types.ts`

---

## Prompt 12.2: Add Sandbox Validation Utilities

### Context
We need path validation in TypeScript that mirrors the Python sandbox.py logic. Security is critical.

### Task
Create `src/sandbox-utils.ts`:

```typescript
/**
 * Sandbox path validation utilities.
 * SECURITY CRITICAL: These functions gate all draft file operations.
 */

import * as path from 'path';
import * as fs from 'fs';
import * as crypto from 'crypto';

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
    if (!resolved.startsWith(workspaceResolved + path.sep)) {
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
```

### File Location
`/Users/eriksjaastad/projects/_tools/ollama-mcp/src/sandbox-utils.ts`

---

## Prompt 12.3: Implement Draft Tools

### Context
Now we implement the actual MCP tools. These call the validation utilities and perform file operations.

### Task
Create `src/draft-tools.ts`:

```typescript
/**
 * Draft tools for Sandbox Draft Pattern (V4).
 * These tools allow local models to edit files in a controlled sandbox.
 */

import * as fs from 'fs';
import * as path from 'path';
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
  getSandboxDir,
} from './sandbox-utils.js';

// Default workspace root - can be overridden
const DEFAULT_WORKSPACE = path.resolve(__dirname, '../../agent-hub');

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

    // Copy source to draft
    const sourceContent = fs.readFileSync(readValidation.resolvedPath!, 'utf-8');
    fs.writeFileSync(draftPath, sourceContent, 'utf-8');

    // Compute hash and line count
    const originalHash = computeFileHash(readValidation.resolvedPath!);
    const lineCount = sourceContent.split('\n').length;

    console.log(`Draft created: ${draftPath}`);

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

    console.log(`Draft updated: ${draft_path}`);

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

    console.log(`Draft submitted: ${submissionPath}`);

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
```

### File Location
`/Users/eriksjaastad/projects/_tools/ollama-mcp/src/draft-tools.ts`

---

## Prompt 12.4: Register Tools in Server

### Context
The draft tools need to be registered in the MCP server so they're available to clients.

### Task
Update `src/server.ts` to include the draft tools:

**Step 1:** Add imports at the top of the file:
```typescript
import {
  requestDraft,
  writeDraft,
  readDraft,
  submitDraft,
} from './draft-tools.js';
```

**Step 2:** Add tool definitions to the `tools` array in the `listTools` handler:
```typescript
{
  name: "ollama_request_draft",
  description: "Request a copy of a file to edit in the sandbox. Returns the draft path for subsequent edits.",
  inputSchema: {
    type: "object",
    properties: {
      source_path: {
        type: "string",
        description: "Path to the source file to draft"
      },
      task_id: {
        type: "string",
        description: "Current task identifier"
      }
    },
    required: ["source_path", "task_id"]
  }
},
{
  name: "ollama_write_draft",
  description: "Write content to a draft file. Can ONLY write to sandbox drafts directory.",
  inputSchema: {
    type: "object",
    properties: {
      draft_path: {
        type: "string",
        description: "Path to the draft file (must be in sandbox)"
      },
      content: {
        type: "string",
        description: "New content for the draft"
      }
    },
    required: ["draft_path", "content"]
  }
},
{
  name: "ollama_read_draft",
  description: "Read the current content of a draft file.",
  inputSchema: {
    type: "object",
    properties: {
      draft_path: {
        type: "string",
        description: "Path to the draft file"
      }
    },
    required: ["draft_path"]
  }
},
{
  name: "ollama_submit_draft",
  description: "Submit a completed draft for Floor Manager review. Creates submission metadata.",
  inputSchema: {
    type: "object",
    properties: {
      draft_path: {
        type: "string",
        description: "Path to the completed draft"
      },
      original_path: {
        type: "string",
        description: "Path to the original file"
      },
      task_id: {
        type: "string",
        description: "Current task identifier"
      },
      change_summary: {
        type: "string",
        description: "Brief description of changes made"
      }
    },
    required: ["draft_path", "original_path", "task_id", "change_summary"]
  }
}
```

**Step 3:** Add tool call handlers in the `callTool` handler's switch statement:
```typescript
case "ollama_request_draft": {
  const result = requestDraft(args as any);
  return {
    content: [{
      type: "text",
      text: JSON.stringify(result, null, 2)
    }]
  };
}

case "ollama_write_draft": {
  const result = writeDraft(args as any);
  return {
    content: [{
      type: "text",
      text: JSON.stringify(result, null, 2)
    }]
  };
}

case "ollama_read_draft": {
  const result = readDraft(args as any);
  return {
    content: [{
      type: "text",
      text: JSON.stringify(result, null, 2)
    }]
  };
}

case "ollama_submit_draft": {
  const result = submitDraft(args as any);
  return {
    content: [{
      type: "text",
      text: JSON.stringify(result, null, 2)
    }]
  };
}
```

### File Location
`/Users/eriksjaastad/projects/_tools/ollama-mcp/src/server.ts`

---

## Prompt 12.5: Build and Test

### Context
After adding the tools, we need to build and verify they work.

### Task
**Step 1:** Build the project:
```bash
cd /Users/eriksjaastad/projects/_tools/ollama-mcp
npm run build
```

**Step 2:** Create a test script `scripts/test_draft_tools.js`:
```javascript
#!/usr/bin/env node
/**
 * Test script for draft tools.
 * Verifies the sandbox security and basic functionality.
 */

const path = require('path');
const fs = require('fs');

// Import the built modules
const { requestDraft, writeDraft, readDraft, submitDraft } = require('../dist/draft-tools.js');
const { validateSandboxWrite, getSandboxDir } = require('../dist/sandbox-utils.js');

console.log('='.repeat(50));
console.log('DRAFT TOOLS TEST');
console.log('='.repeat(50));
console.log();

let passed = 0;
let failed = 0;

function test(name, fn) {
  try {
    fn();
    console.log(`✓ ${name}`);
    passed++;
  } catch (error) {
    console.log(`✗ ${name}: ${error.message}`);
    failed++;
  }
}

// Test 1: Sandbox validation blocks outside paths
test('Blocks writes outside sandbox', () => {
  const result = validateSandboxWrite('/tmp/evil.draft');
  if (result.valid) throw new Error('Should block /tmp');
});

// Test 2: Sandbox validation blocks path traversal
test('Blocks path traversal', () => {
  const sandboxDir = getSandboxDir();
  const result = validateSandboxWrite(path.join(sandboxDir, '..', '..', 'escape.draft'));
  if (result.valid) throw new Error('Should block traversal');
});

// Test 3: Sandbox validation allows valid paths
test('Allows valid sandbox paths', () => {
  const sandboxDir = getSandboxDir();
  const result = validateSandboxWrite(path.join(sandboxDir, 'test.task1.draft'));
  if (!result.valid) throw new Error(`Should allow: ${result.reason}`);
});

// Test 4: Request draft fails for nonexistent file
test('Request draft fails for missing file', () => {
  const result = requestDraft({
    source_path: '/nonexistent/file.py',
    task_id: 'test_missing'
  });
  if (result.success) throw new Error('Should fail for missing file');
});

// Test 5: Write draft fails outside sandbox
test('Write draft fails outside sandbox', () => {
  const result = writeDraft({
    draft_path: '/tmp/evil.draft',
    content: 'malicious content'
  });
  if (result.success) throw new Error('Should block write outside sandbox');
});

console.log();
console.log('='.repeat(50));
console.log(`RESULTS: ${passed} passed, ${failed} failed`);
console.log('='.repeat(50));

if (failed > 0) {
  console.log('\nPhase 12 has issues - review failures above.');
  process.exit(1);
} else {
  console.log('\nPhase 12 security tests PASSED.');
  console.log('Ready for Phase 13 (Floor Manager Draft Gate).');
  process.exit(0);
}
```

**Step 3:** Run the test:
```bash
node scripts/test_draft_tools.js
```

### File Location
`/Users/eriksjaastad/projects/_tools/ollama-mcp/scripts/test_draft_tools.js`

---

## Execution Order

1. **12.1** - Create draft types
2. **12.2** - Create sandbox utilities
3. **12.3** - Implement draft tools
4. **12.4** - Register in server.ts
5. **12.5** - Build and test

### Verification

```bash
# After all prompts:
cd /Users/eriksjaastad/projects/_tools/ollama-mcp

# Build
npm run build

# Run tests
node scripts/test_draft_tools.js

# List tools to verify registration
# (This requires running the MCP server and using inspector)
```

---

## Success Criteria

Phase 12 is DONE when:
- [x] `npm run build` succeeds with no errors
- [x] All four draft tools are registered in server.ts
- [x] Security tests pass (escape attempts blocked)
- [x] `ollama_request_draft` can copy a file to sandbox
- [x] `ollama_write_draft` can update draft content
- [x] `ollama_submit_draft` creates submission metadata

---

## Security Checklist

Before marking Phase 12 complete, verify:
- [x] `validateSandboxWrite()` blocks ALL paths outside sandbox
- [x] Path traversal is blocked in TypeScript implementation
- [x] Sensitive files cannot be drafted
- [x] Atomic writes used (tmp + rename)
- [x] All errors are logged

**Status: COMPLETE** (Committed: `86af952`)

---

*Phase 12 gives Ollama the tools. Phase 13 gives Floor Manager the gate.*
