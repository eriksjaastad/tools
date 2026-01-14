import { appendFileSync, mkdirSync } from "fs";
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

/**
 * Log a model run to JSON Lines file
 * Each entry is a single line of JSON for easy parsing
 */
export function logRun(metadata: RunMetadata): void {
  try {
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

