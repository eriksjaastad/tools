import { describe, it, expect } from 'vitest';
import { safePath } from '../src/tools/claude_security_audit';
import { resolve } from 'path';

describe('Path Traversal Protection', () => {
    it('should block parent directory traversal', () => {
        expect(safePath('/workspace', '../etc/passwd')).toBeNull();
        expect(safePath('/workspace', '../../etc/passwd')).toBeNull();
        expect(safePath('/workspace', 'foo/../../../etc/passwd')).toBeNull();
    });

    it('should allow valid relative paths', () => {
        // Use resolve to handle OS differences (like /private/tmp on mac)
        const base = '/tmp/workspace';
        expect(safePath(base, 'src/index.ts')).toBe(resolve(base, 'src/index.ts'));
        expect(safePath(base, './src/index.ts')).toBe(resolve(base, 'src/index.ts'));
    });

    it('should block absolute paths', () => {
        expect(safePath('/workspace', '/etc/passwd')).toBeNull();
    });
});
