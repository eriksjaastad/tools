#!/usr/bin/env node
/**
 * Security tests for sandbox path validation.
 * Run: node scripts/test_sandbox_security.js
 */

import path from 'path';
import { validateSandboxWrite, validateSourceRead, getSandboxDir } from '../dist/sandbox-utils.js';

const sandboxDir = getSandboxDir();
const workspaceRoot = process.cwd();

const tests = [
    // Path traversal attacks
    {
        name: 'Block parent traversal',
        fn: () => validateSandboxWrite('../../../etc/passwd'),
        expect: { valid: false }
    },
    {
        name: 'Block encoded traversal',
        fn: () => validateSandboxWrite('..%2F..%2Fetc/passwd'),
        expect: { valid: false }
    },
    {
        name: 'Block double-encoded',
        fn: () => validateSandboxWrite('..%252F..%252Fetc/passwd'),
        expect: { valid: false }
    },
    {
        name: 'Block null byte injection',
        fn: () => validateSandboxWrite(path.join(sandboxDir, 'file.draft\x00.sh')),
        expect: { valid: false }
    },

    // Extension attacks
    {
        name: 'Block .sh extension',
        fn: () => validateSandboxWrite(path.join(sandboxDir, 'malicious.sh')),
        expect: { valid: false }
    },
    {
        name: 'Block .py extension',
        fn: () => validateSandboxWrite(path.join(sandboxDir, 'script.py')),
        expect: { valid: false }
    },

    // Valid cases
    {
        name: 'Allow .draft extension',
        fn: () => validateSandboxWrite(path.join(sandboxDir, 'test.draft')),
        expect: { valid: true }
    },
    {
        name: 'Allow .submission.json',
        fn: () => validateSandboxWrite(path.join(sandboxDir, 'task123.submission.json')),
        expect: { valid: true }
    },

    // Sensitive file reads
    {
        name: 'Block .env read',
        fn: () => validateSourceRead(path.join(workspaceRoot, '.env'), workspaceRoot),
        expect: { valid: false }
    },
    {
        name: 'Block credentials.json',
        fn: () => validateSourceRead(path.join(workspaceRoot, 'credentials.json'), workspaceRoot),
        expect: { valid: false }
    },
];

let passed = 0;
let failed = 0;

console.log('Running sandbox security tests...\n');

for (const test of tests) {
    try {
        const result = test.fn();
        const success = result.valid === test.expect.valid;

        if (success) {
            console.log(`  ✅ ${test.name}`);
            passed++;
        } else {
            console.log(`  ❌ ${test.name}`);
            console.log(`     Expected valid=${test.expect.valid}, got valid=${result.valid}`);
            console.log(`     Reason: ${result.reason}`);
            failed++;
        }
    } catch (error) {
        console.log(`  ❌ ${test.name}`);
        console.log(`     Error: ${error.message}`);
        failed++;
    }
}

console.log(`\n${passed} passed, ${failed} failed`);
process.exit(failed > 0 ? 1 : 0);
