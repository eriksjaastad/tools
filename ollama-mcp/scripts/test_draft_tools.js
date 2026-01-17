#!/usr/bin/env node
/**
 * Test script for draft tools.
 * Verifies the sandbox security and basic functionality.
 */

import path from 'path';
import fs from 'fs';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Import the built modules
// Note: Using relative paths to the built files in dist
const { requestDraft, writeDraft, readDraft, submitDraft } = await import('../dist/draft-tools.js');
const { validateSandboxWrite, getSandboxDir } = await import('../dist/sandbox-utils.js');

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
