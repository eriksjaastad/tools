#!/usr/bin/env node
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import { spawn } from "child_process";
import { promisify } from "util";
import { readFileSync, createReadStream } from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";
import readline from "readline";
import yaml from "js-yaml";
import { logRun, generateBatchId } from "./logger.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const sleep = promisify(setTimeout);

// Safety constants
const OLLAMA_EXECUTABLE = "ollama";
const MAX_PROMPT_LENGTH = 100000;
const MAX_NUM_PREDICT = 8192;
const DEFAULT_TIMEOUT_MS = 120000; // 120s
const DEFAULT_CONCURRENCY = 3;
const MAX_CONCURRENCY = 8;

// Routing defaults
const DEFAULT_CHAINS: Record<string, string[]> = {
  classification: ["llama3.2:3b", "qwen3:14b"],
  extraction: ["llama3.2:3b", "qwen3:14b"],
  code: ["qwen3:14b", "deepseek-r1:14b"],
  reasoning: ["deepseek-r1:14b", "qwen3:14b"],
  file_mod: ["qwen3:14b", "deepseek-r1:14b"],
  auto: ["qwen3:14b", "deepseek-r1:14b", "llama3.2:3b"],
};

// Load routing config (SSOT)
const CONFIG_PATH = join(__dirname, "..", "config", "routing.yaml");
interface RoutingConfig {
  default_model: string;
  fallback_chains: Record<string, string[]>;
  telemetry_review: {
    last_review: string;
    review_interval_days: number;
    min_runs_before_review: number;
  };
}

let routingConfig: RoutingConfig = {
  default_model: "qwen3:14b",
  fallback_chains: DEFAULT_CHAINS,
  telemetry_review: {
    last_review: "2026-01-10",
    review_interval_days: 30,
    min_runs_before_review: 50,
  },
};

try {
  const fileContents = readFileSync(CONFIG_PATH, "utf8");
  const loaded = yaml.load(fileContents) as any;
  if (loaded && loaded.fallback_chains) {
    routingConfig = { ...routingConfig, ...loaded };
  }
} catch (e) {
  console.error("Notice: Using default routing (config/routing.yaml not found or invalid)");
}

interface OllamaRunOptions {
  temperature?: number;
  num_predict?: number;
  system?: string;
  timeout?: number;
}

interface OllamaJob {
  model?: string;
  prompt: string;
  options?: OllamaRunOptions;
  task_type?: "classification" | "extraction" | "code" | "reasoning" | "file_mod" | "auto";
}

interface OllamaResult {
  stdout: string;
  stderr: string;
  exitCode: number;
  error?: string;
  metadata?: {
    model_used: string;
    task_type: string;
    duration_ms: number;
    timed_out: boolean;
    models_tried: string[];
    escalate: boolean;
    escalation_reason?: string;
    telemetry_review_due: boolean;
    runs_since_last_review: number;
  };
}

/**
 * Checks if a telemetry review is due based on date and number of runs.
 */
async function checkTelemetryReviewDue(): Promise<{ due: boolean; runsSinceReview: number }> {
  const telemetryPath = join(process.env.HOME || "", ".ollama-mcp", "runs.jsonl");
  let runsSinceReview = 0;
  const lastReviewDate = new Date(routingConfig.telemetry_review.last_review);

  try {
    const fileStream = createReadStream(telemetryPath);
    const rl = readline.createInterface({
      input: fileStream,
      crlfDelay: Infinity,
    });

    for await (const line of rl) {
      if (!line.trim()) continue;
      try {
        const run = JSON.parse(line);
        const runDate = new Date(run.timestamp);
        if (runDate >= lastReviewDate) {
          runsSinceReview++;
        }
      } catch (e) {
        // Skip malformed lines
      }
    }
  } catch (e) {
    // File not found or other read error, return defaults
    return { due: false, runsSinceReview: 0 };
  }

  const daysSinceReview = (Date.now() - lastReviewDate.getTime()) / (1000 * 60 * 60 * 24);
  const due =
    daysSinceReview >= routingConfig.telemetry_review.review_interval_days &&
    runsSinceReview >= routingConfig.telemetry_review.min_runs_before_review;

  return { due, runsSinceReview };
}

// Port from AI Router - detect bad responses
function isGoodResponse(text: string, taskType: string): boolean {
  // Too short (unless it's a classification or extraction task)
  const minLength = taskType === "classification" || taskType === "extraction" ? 1 : 40;
  if (text.trim().length < minLength) return false;

  // Refusal patterns
  const refusals = ["I cannot", "I'm unable", "I don't have access"];
  if (refusals.some((r) => text.toLowerCase().includes(r.toLowerCase()))) return false;

  // Empty or error
  if (!text.trim()) return false;

  return true;
}

// Validate inputs
function validateModel(model: string): void {
  if (!model || typeof model !== "string" || model.trim().length === 0) {
    throw new Error("Model name must be a non-empty string");
  }
  // Prevent command injection
  if (model.includes(";") || model.includes("&") || model.includes("|")) {
    throw new Error("Invalid model name");
  }
}

function validatePrompt(prompt: string): void {
  if (typeof prompt !== "string") {
    throw new Error("Prompt must be a string");
  }
  if (prompt.length > MAX_PROMPT_LENGTH) {
    throw new Error(`Prompt exceeds maximum length of ${MAX_PROMPT_LENGTH}`);
  }
}

function validateOptions(options?: OllamaRunOptions): void {
  if (!options) return;
  
  if (options.num_predict !== undefined) {
    if (typeof options.num_predict !== "number" || options.num_predict < 1 || options.num_predict > MAX_NUM_PREDICT) {
      throw new Error(`num_predict must be between 1 and ${MAX_NUM_PREDICT}`);
    }
  }
  
  if (options.temperature !== undefined) {
    if (typeof options.temperature !== "number" || options.temperature < 0 || options.temperature > 2) {
      throw new Error("temperature must be between 0 and 2");
    }
  }
}

async function ollamaListModels(): Promise<string[]> {
  return new Promise((resolve, reject) => {
    const proc = spawn(OLLAMA_EXECUTABLE, ["list"]);

    let stdout = "";
    let stderr = "";

    proc.stdout.on("data", (data) => {
      stdout += data.toString();
    });

    proc.stderr.on("data", (data) => {
      stderr += data.toString();
    });

    proc.on("close", (code) => {
      if (code !== 0) {
        reject(new Error(`Ollama list failed: ${stderr}`));
        return;
      }

      // Parse output: skip header line, extract model names
      const lines = stdout.trim().split("\n");
      const models = lines
        .slice(1) // Skip header
        .map((line) => line.split(/\s+/)[0]) // First column is model name
        .filter((name) => name && name.length > 0);

      resolve(models);
    });

    proc.on("error", (err) => {
      reject(new Error(`Failed to execute ollama: ${err.message}`));
    });
  });
}

// Run a single model
async function ollamaRun(
  model: string,
  prompt: string,
  options?: OllamaRunOptions,
  batchId?: string,
  concurrency?: number,
  task_type?: string
): Promise<OllamaResult> {
  validateModel(model);
  validatePrompt(prompt);
  validateOptions(options);

  const timeout = options?.timeout || DEFAULT_TIMEOUT_MS;
  const args = ["run", model];
  
  // Capture start time for logging
  const startTime = new Date().toISOString();
  const startMs = Date.now();

  // Note: ollama CLI doesn't support temperature/num_predict directly via flags
  // These would need to be set via Modelfile or API
  // For now, we just use basic run command
  
  // Prepend system prompt if provided
  let fullPrompt = prompt;
  if (options?.system) {
    fullPrompt = `${options.system}\n\n${prompt}`;
  }

  return new Promise((resolve) => {
    const proc = spawn(OLLAMA_EXECUTABLE, args);

    let stdout = "";
    let stderr = "";
    let timedOut = false;

    // Send prompt via stdin with newline
    proc.stdin.write(fullPrompt + "\n");
    proc.stdin.end();

    proc.stdout.on("data", (data) => {
      stdout += data.toString();
    });

    proc.stderr.on("data", (data) => {
      stderr += data.toString();
    });

    const timeoutHandle = setTimeout(() => {
      timedOut = true;
      proc.kill("SIGTERM");
    }, timeout);

    proc.on("close", (code) => {
      clearTimeout(timeoutHandle);
      
      // Capture end time and log metrics
      const endTime = new Date().toISOString();
      const durationMs = Date.now() - startMs;
      
      logRun({
        timestamp: startTime,
        model,
        start: startTime,
        end: endTime,
        duration_ms: durationMs,
        exit_code: timedOut ? -1 : (code ?? -1),
        output_chars: stdout.length,
        timed_out: timedOut,
        batch_id: batchId,
        concurrency: concurrency,
        task_type: task_type,
      });
      
      if (timedOut) {
        resolve({
          stdout: stdout,
          stderr: stderr + "\nProcess timed out",
          exitCode: -1,
          error: "Timeout exceeded",
          metadata: {
            model_used: model,
            task_type: task_type || "auto",
            duration_ms: durationMs,
            timed_out: true,
            models_tried: [model],
            escalate: false,
            telemetry_review_due: false,
            runs_since_last_review: 0,
          }
        });
      } else {
        resolve({
          stdout,
          stderr,
          exitCode: code ?? -1,
          metadata: {
            model_used: model,
            task_type: task_type || "auto",
            duration_ms: durationMs,
            timed_out: false,
            models_tried: [model],
            escalate: false,
            telemetry_review_due: false,
            runs_since_last_review: 0,
          }
        });
      }
    });

    proc.on("error", (err) => {
      clearTimeout(timeoutHandle);
      
      // Log error case
      const endTime = new Date().toISOString();
      const durationMs = Date.now() - startMs;
      
      logRun({
        timestamp: startTime,
        model,
        start: startTime,
        end: endTime,
        duration_ms: durationMs,
        exit_code: -1,
        output_chars: stdout.length,
        timed_out: false,
        batch_id: batchId,
        concurrency: concurrency,
        task_type: task_type,
      });
      
      resolve({
        stdout,
        stderr: stderr + "\n" + err.message,
        exitCode: -1,
        error: err.message,
        metadata: {
          model_used: model,
          task_type: task_type || "auto",
          duration_ms: durationMs,
          timed_out: false,
          models_tried: [model],
          escalate: false,
          telemetry_review_due: false,
          runs_since_last_review: 0,
        }
      });
    });
  });
}

// Run a single model with smart routing and fallback
async function ollamaRunWithRouting(
  job: OllamaJob,
  batchId?: string,
  concurrency?: number
): Promise<OllamaResult> {
  const { model, prompt, options, task_type } = job;

  // Resolve fallback chain (SSOT from routingConfig)
  let chain: string[] = [];
  if (model) {
    chain = [model];
  } else if (task_type && routingConfig.fallback_chains[task_type]) {
    chain = routingConfig.fallback_chains[task_type];
  } else {
    // Default to auto or a balanced model from config
    chain = routingConfig.fallback_chains["auto"] || [routingConfig.default_model || "qwen3:14b"];
  }

  const modelsTried: string[] = [];
  let lastResult: OllamaResult | null = null;
  const telemetryStatus = await checkTelemetryReviewDue();

  for (const targetModel of chain) {
    modelsTried.push(targetModel);
    const result = await ollamaRun(targetModel, prompt, options, batchId, concurrency, task_type);
    lastResult = result;

    // Check for success and quality
    if (result.exitCode === 0 && !result.error && isGoodResponse(result.stdout, task_type || "auto")) {
      return {
        ...result,
        metadata: {
          ...result.metadata!,
          task_type: task_type || "auto",
          models_tried: modelsTried,
          telemetry_review_due: telemetryStatus.due,
          runs_since_last_review: telemetryStatus.runsSinceReview,
        },
      };
    }

    console.error(`[routing] Model ${targetModel} failed or gave poor response. Trying next in chain...`);
  }

  // If all failed or were poor, return last result with escalation flag
  return {
    stdout: lastResult?.stdout || "",
    stderr: (lastResult?.stderr || "") + "\nAll local models in fallback chain failed or gave poor responses",
    exitCode: lastResult?.exitCode ?? -1,
    error: "All local models in fallback chain failed or gave poor responses",
    metadata: {
      model_used: modelsTried[modelsTried.length - 1],
      task_type: task_type || "auto",
      duration_ms: lastResult?.metadata?.duration_ms || 0,
      timed_out: lastResult?.metadata?.timed_out || false,
      models_tried: modelsTried,
      escalate: true,
      escalation_reason: "all_local_models_failed",
      telemetry_review_due: telemetryStatus.due,
      runs_since_last_review: telemetryStatus.runsSinceReview,
    },
  };
}

// Run many models concurrently with a limit
async function ollamaRunMany(
  jobs: OllamaJob[],
  maxConcurrency: number = DEFAULT_CONCURRENCY
): Promise<OllamaResult[]> {
  // Validate concurrency
  const concurrency = Math.min(
    Math.max(1, maxConcurrency),
    MAX_CONCURRENCY
  );

  // Validate all jobs first
  for (const job of jobs) {
    if (job.model) validateModel(job.model);
    validatePrompt(job.prompt);
    validateOptions(job.options);
  }

  // Generate batch ID for grouping these runs
  const batchId = generateBatchId();

  const results: OllamaResult[] = new Array(jobs.length);
  const queue = jobs.map((job, index) => ({ job, index }));
  let activeCount = 0;
  let queueIndex = 0;

  return new Promise((resolve) => {
    const processNext = () => {
      if (queueIndex >= queue.length && activeCount === 0) {
        resolve(results);
        return;
      }

      while (activeCount < concurrency && queueIndex < queue.length) {
        const { job, index } = queue[queueIndex];
        queueIndex++;
        activeCount++;

        ollamaRunWithRouting(job, batchId, concurrency).then((result) => {
          results[index] = result;
          activeCount--;
          processNext();
        });
      }
    };

    processNext();
  });
}

// Create and start MCP server
const server = new Server(
  {
    name: "ollama-mcp",
    version: "1.0.0",
  },
  {
    capabilities: {
      tools: {},
    },
  }
);

// Register tool handlers
server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: [
      {
        name: "ollama_list_models",
        description: "List all locally available Ollama models",
        inputSchema: {
          type: "object",
          properties: {},
        },
      },
      {
        name: "ollama_run",
        description: "Run a single Ollama model with a prompt",
        inputSchema: {
          type: "object",
          properties: {
            model: {
              type: "string",
              description: "Name of the Ollama model to run (bypasses smart routing if provided)",
            },
            prompt: {
              type: "string",
              description: "Prompt to send to the model",
            },
            task_type: {
              type: "string",
              enum: ["classification", "extraction", "code", "reasoning", "file_mod", "auto"],
              description: "Type of task for smart routing",
            },
            options: {
              type: "object",
              description: "Optional parameters for the model",
              properties: {
                temperature: {
                  type: "number",
                  description: "Temperature (0-2)",
                },
                num_predict: {
                  type: "number",
                  description: "Maximum tokens to generate",
                },
                system: {
                  type: "string",
                  description: "System prompt",
                },
                timeout: {
                  type: "number",
                  description: "Timeout in milliseconds (default: 120000)",
                },
              },
            },
          },
          required: ["prompt"],
        },
      },
      {
        name: "ollama_run_many",
        description: "Run multiple Ollama models concurrently with a limit",
        inputSchema: {
          type: "object",
          properties: {
            jobs: {
              type: "array",
              description: "Array of jobs to run",
              items: {
                type: "object",
                properties: {
                  model: {
                    type: "string",
                    description: "Model name (optional if task_type provided)",
                  },
                  prompt: {
                    type: "string",
                    description: "Prompt text",
                  },
                  task_type: {
                    type: "string",
                    enum: ["classification", "extraction", "code", "reasoning", "file_mod", "auto"],
                    description: "Type of task for smart routing",
                  },
                  options: {
                    type: "object",
                    description: "Optional parameters",
                    properties: {
                      temperature: { type: "number" },
                      num_predict: { type: "number" },
                      system: { type: "string" },
                      timeout: { type: "number" },
                    },
                  },
                },
                required: ["prompt"],
              },
            },
            maxConcurrency: {
              type: "number",
              description: `Maximum concurrent jobs (default: ${DEFAULT_CONCURRENCY}, max: ${MAX_CONCURRENCY})`,
            },
          },
          required: ["jobs"],
        },
      },
    ],
  };
});

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  try {
    switch (request.params.name) {
      case "ollama_list_models": {
        const models = await ollamaListModels();
        return {
          content: [
            {
              type: "text",
              text: JSON.stringify({ models }, null, 2),
            },
          ],
        };
      }

      case "ollama_run": {
        const { model, prompt, options, task_type } = request.params.arguments as {
          model?: string;
          prompt: string;
          options?: OllamaRunOptions;
          task_type?: "classification" | "extraction" | "code" | "reasoning" | "file_mod" | "auto";
        };
        
        console.error(`[ollama_run] task_type=${task_type || 'none'}, model=${model || 'auto'}`);
        const result = await ollamaRunWithRouting({ model, prompt, options, task_type });
        
        return {
          content: [
            {
              type: "text",
              text: JSON.stringify(result, null, 2),
            },
          ],
          isError: result.metadata?.escalate,
        };
      }

      case "ollama_run_many": {
        const { jobs, maxConcurrency } = request.params.arguments as {
          jobs: OllamaJob[];
          maxConcurrency?: number;
        };
        
        console.error(`[ollama_run_many] jobs=${jobs.length}, concurrency=${maxConcurrency || DEFAULT_CONCURRENCY}`);
        const results = await ollamaRunMany(jobs, maxConcurrency);
        
        return {
          content: [
            {
              type: "text",
              text: JSON.stringify({ results }, null, 2),
            },
          ],
        };
      }

      default:
        throw new Error(`Unknown tool: ${request.params.name}`);
    }
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    return {
      content: [
        {
          type: "text",
          text: JSON.stringify({ error: errorMessage }, null, 2),
        },
      ],
      isError: true,
    };
  }
});

// Start server
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error("Ollama MCP server running on stdio");
}

main().catch((error) => {
  console.error("Fatal error:", error);
  process.exit(1);
});

