/**
 * claude_health: Check if Claude CLI is available
 */

import { spawn } from 'child_process';

export async function claudeHealth(_args: Record<string, unknown>): Promise<{
  available: boolean;
  version?: string;
  error?: string;
}> {
  return new Promise((resolve) => {
    const HEALTH_CHECK_TIMEOUT_MS = 30000; // 30 seconds

    const proc = spawn('claude', ['--version'], {
      stdio: ['pipe', 'pipe', 'pipe']
    });

    const timeoutId = setTimeout(() => {
      proc.kill('SIGTERM');
      resolve({
        available: false,
        error: `Health check timed out after ${HEALTH_CHECK_TIMEOUT_MS / 1000}s`
      });
    }, HEALTH_CHECK_TIMEOUT_MS);

    let stdout = '';
    let stderr = '';

    proc.stdout.on('data', (data) => {
      stdout += data.toString();
    });

    proc.stderr.on('data', (data) => {
      stderr += data.toString();
    });

    proc.on('error', (err) => {
      clearTimeout(timeoutId);
      resolve({
        available: false,
        error: `Claude CLI not found: ${err.message}`
      });
    });

    proc.on('close', (code) => {
      clearTimeout(timeoutId);
      if (code === 0) {
        resolve({
          available: true,
          version: stdout.trim()
        });
      } else {
        resolve({
          available: false,
          error: stderr || `Exit code: ${code}`
        });
      }
    });
  });
}
