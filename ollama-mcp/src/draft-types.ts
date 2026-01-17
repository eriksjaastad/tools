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
