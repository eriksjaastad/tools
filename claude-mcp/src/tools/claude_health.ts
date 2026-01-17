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
    const proc = spawn('claude', ['--version'], {
      stdio: ['pipe', 'pipe', 'pipe']
    });

    let stdout = '';
    let stderr = '';

    proc.stdout.on('data', (data) => {
      stdout += data.toString();
    });

    proc.stderr.on('data', (data) => {
      stderr += data.toString();
    });

    proc.on('error', (err) => {
      resolve({
        available: false,
        error: `Claude CLI not found: ${err.message}`
      });
    });

    proc.on('close', (code) => {
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
