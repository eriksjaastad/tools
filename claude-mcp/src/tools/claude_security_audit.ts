/**
 * claude_security_audit: Deep security review of specific files
 *
 * Goes beyond what DeepSeek catches - looks for logic flaws, injection risks, etc.
 */

import { spawn } from 'child_process';
import { readFileSync, existsSync } from 'fs';

interface SecurityAuditArgs {
  files: string[];
  working_directory?: string;
  timeout_seconds?: number;
}

interface SecurityAuditResult {
  success: boolean;
  findings?: Array<{
    severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
    file: string;
    line?: number;
    description: string;
    recommendation: string;
  }>;
  error?: string;
  duration_ms: number;
}

const SECURITY_PROMPT_TEMPLATE = `
You are performing a security audit of the following files.

## Files to Review

{{FILES_CONTENT}}

## Security Checklist

Check for:
1. Hardcoded secrets (API keys, passwords, tokens)
2. SQL injection vulnerabilities
3. Command injection risks
4. XSS vulnerabilities
5. Path traversal attacks
6. Insecure deserialization
7. Missing input validation
8. Improper error handling that leaks info
9. Insecure cryptographic practices
10. Race conditions

## Required Output

Respond with ONLY this JSON (no other text):

{
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM|LOW",
      "file": "path/to/file",
      "line": 42,
      "description": "What the issue is",
      "recommendation": "How to fix it"
    }
  ]
}

If no issues found, return: {"findings": []}
`;

export async function claudeSecurityAudit(args: Record<string, unknown>): Promise<SecurityAuditResult> {
  const startTime = Date.now();
  const {
    files,
    working_directory = process.cwd(),
    timeout_seconds = 300
  } = args as SecurityAuditArgs;

  // Read all files
  let filesContent = '';
  for (const file of files) {
    const fullPath = `${working_directory}/${file}`;
    if (existsSync(fullPath)) {
      const content = readFileSync(fullPath, 'utf-8');
      filesContent += `\n### ${file}\n\`\`\`\n${content}\n\`\`\`\n`;
    } else {
      filesContent += `\n### ${file}\n(File not found)\n`;
    }
  }

  const prompt = SECURITY_PROMPT_TEMPLATE.replace('{{FILES_CONTENT}}', filesContent);

  return new Promise((resolve) => {
    const proc = spawn('claude', ['--dangerously-skip-permissions', '--print'], {
      cwd: working_directory,
      stdio: ['pipe', 'pipe', 'pipe']
    });

    const timeoutId = setTimeout(() => {
      proc.kill('SIGTERM');
      resolve({
        success: false,
        error: 'Security audit timed out',
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
            findings: result.findings || [],
            duration_ms: Date.now() - startTime
          });
        } else {
          resolve({
            success: false,
            error: 'Could not parse audit response',
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
