import { appendFileSync, mkdirSync, existsSync, statSync, renameSync, unlinkSync } from "fs";
import { homedir } from "os";
import { join } from "path";

// Log directory in user's home folder
const LOG_DIR = join(homedir(), ".ollama-mcp");
const LOG_FILE = join(LOG_DIR, "runs.jsonl");

// Ensure log directory exists
try {
  mkdirSync(LOG_DIR, { recursive: true });
} catch (error) {
  // Directory already exists, ignore
}

interface RunMetadata {
  timestamp: string;
  model: string;
  start: string;
  end: string;
  duration_ms: number;
  exit_code: number;
  output_chars: number;
  timed_out: boolean;
  task_type?: string;
  batch_id?: string;
  concurrency?: number;
}

const MAX_LOG_SIZE_BYTES = 10 * 1024 * 1024; // 10MB
const MAX_ROTATED_FILES = 5;

function rotateLogIfNeeded(logPath: string): void {
  try {
    if (!existsSync(logPath)) return;

    const stats = statSync(logPath);
    if (stats.size < MAX_LOG_SIZE_BYTES) return;

    // Rotate existing files
    for (let i = MAX_ROTATED_FILES - 1; i >= 1; i--) {
      const oldPath = `${logPath}.${i}`;
      const newPath = `${logPath}.${i + 1}`;
      if (existsSync(oldPath)) {
        if (i === MAX_ROTATED_FILES - 1) {
          unlinkSync(oldPath); // Delete oldest
        } else {
          renameSync(oldPath, newPath);
        }
      }
    }

    // Rotate current to .1
    renameSync(logPath, `${logPath}.1`);
    console.log(`Rotated log file: ${logPath}`);
  } catch (error) {
    console.error(`[logger] Log rotation failed: ${error}`);
    // Don't throw - logging should never break the main flow
  }
}

/**
 * Log a model run to JSON Lines file
 * Each entry is a single line of JSON for easy parsing
 */
export function logRun(metadata: RunMetadata): void {
  try {
    rotateLogIfNeeded(LOG_FILE);
    const jsonLine = JSON.stringify(metadata) + "\n";
    appendFileSync(LOG_FILE, jsonLine, "utf8");
  } catch (error) {
    // Log to stderr but don't crash the server
    console.error("[logger] Failed to write log:", error);
  }
}

/**
 * Generate a unique batch ID for ollama_run_many jobs
 */
export function generateBatchId(): string {
  return Date.now().toString(36) + Math.random().toString(36).substring(2, 9);
}

/**
 * Get the log file path (useful for analysis scripts)
 */
export function getLogFilePath(): string {
  return LOG_FILE;
}
