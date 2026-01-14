#!/usr/bin/env node
/**
 * Analyze Ollama MCP run logs
 * 
 * Reads ~/.ollama-mcp/runs.jsonl and provides insights:
 * - Average duration per model
 * - Timeout rates
 * - Output size statistics
 * - Batch analysis
 */

import { readFileSync, existsSync } from "fs";
import { homedir } from "os";
import { join } from "path";

const LOG_FILE = join(homedir(), ".ollama-mcp", "runs.jsonl");

/**
 * @typedef {Object} RunLog
 * @property {string} timestamp
 * @property {string} model
 * @property {string} start
 * @property {string} end
 * @property {number} duration_ms
 * @property {number} exit_code
 * @property {number} output_chars
 * @property {boolean} timed_out
 * @property {string} [task_type]
 * @property {string} [batch_id]
 * @property {number} [concurrency]
 */

/**
 * @returns {RunLog[]}
 */
function loadLogs() {
  if (!existsSync(LOG_FILE)) {
    console.error(`No log file found at: ${LOG_FILE}`);
    console.error("Run some Ollama MCP commands first to generate logs.");
    process.exit(1);
  }

  const content = readFileSync(LOG_FILE, "utf8");
  const lines = content.trim().split("\n").filter(line => line.length > 0);
  
  return lines.map((line, index) => {
    try {
      return JSON.parse(line);
    } catch (err) {
      console.error(`Failed to parse line ${index + 1}: ${line}`);
      return null;
    }
  }).filter(log => log !== null);
}

/**
 * @param {RunLog[]} logs
 */
function analyzeByModel(logs) {
  const byModel = new Map();
  
  for (const log of logs) {
    if (!byModel.has(log.model)) {
      byModel.set(log.model, []);
    }
    byModel.get(log.model).push(log);
  }

  console.log("\n📊 Analysis by Model\n" + "=".repeat(80));
  
  for (const [model, modelLogs] of byModel) {
    const totalRuns = modelLogs.length;
    const timeouts = modelLogs.filter(log => log.timed_out).length;
    const timeoutRate = (timeouts / totalRuns * 100).toFixed(1);
    
    const durations = modelLogs.map(log => log.duration_ms);
    const avgDuration = (durations.reduce((a, b) => a + b, 0) / durations.length / 1000).toFixed(1);
    const minDuration = (Math.min(...durations) / 1000).toFixed(1);
    const maxDuration = (Math.max(...durations) / 1000).toFixed(1);
    
    const outputSizes = modelLogs.map(log => log.output_chars);
    const avgOutput = Math.round(outputSizes.reduce((a, b) => a + b, 0) / outputSizes.length);
    
    console.log(`\n🤖 ${model}`);
    console.log(`   Runs: ${totalRuns}`);
    console.log(`   Avg Duration: ${avgDuration}s (min: ${minDuration}s, max: ${maxDuration}s)`);
    console.log(`   Avg Output: ${avgOutput} chars`);
    console.log(`   Timeouts: ${timeouts}/${totalRuns} (${timeoutRate}%)`);
  }
}

/**
 * @param {RunLog[]} logs
 */
function analyzeBatches(logs) {
  const batches = logs.filter(log => log.batch_id);
  
  if (batches.length === 0) {
    console.log("\n\n📦 No batch runs found (ollama_run_many not used yet)");
    return;
  }

  const batchGroups = new Map();
  for (const log of batches) {
    if (!batchGroups.has(log.batch_id)) {
      batchGroups.set(log.batch_id, []);
    }
    batchGroups.get(log.batch_id).push(log);
  }

  console.log("\n\n📦 Batch Analysis (ollama_run_many)\n" + "=".repeat(80));
  console.log(`\nTotal batches: ${batchGroups.size}`);
  
  for (const [batchId, batchLogs] of batchGroups) {
    const concurrency = batchLogs[0].concurrency || 'unknown';
    const models = [...new Set(batchLogs.map(log => log.model))];
    
    const durations = batchLogs.map(log => log.duration_ms);
    const totalTime = (Math.max(...durations) / 1000).toFixed(1);
    const avgJobTime = (durations.reduce((a, b) => a + b, 0) / durations.length / 1000).toFixed(1);
    
    console.log(`\n  Batch ${batchId}:`);
    console.log(`    Jobs: ${batchLogs.length}`);
    console.log(`    Concurrency: ${concurrency}`);
    console.log(`    Models: ${models.join(", ")}`);
    console.log(`    Total wall time: ${totalTime}s`);
    console.log(`    Avg job time: ${avgJobTime}s`);
  }
}

/**
 * @param {RunLog[]} logs
 * @param {number} count
 */
function showRecentRuns(logs, count = 10) {
  console.log(`\n\n🕐 Recent Runs (last ${count})\n` + "=".repeat(80));
  
  const recent = logs.slice(-count).reverse();
  
  for (const log of recent) {
    const duration = (log.duration_ms / 1000).toFixed(1);
    const timestamp = new Date(log.timestamp).toLocaleString();
    const status = log.timed_out ? "⏱️ TIMEOUT" : log.exit_code === 0 ? "✅" : "❌";
    const batch = log.batch_id ? ` [batch: ${log.batch_id.substring(0, 8)}]` : "";
    
    console.log(`\n${status} ${log.model} - ${duration}s - ${log.output_chars} chars${batch}`);
    console.log(`   ${timestamp}`);
  }
}

/**
 * @param {RunLog[]} logs
 */
function showSummary(logs) {
  console.log("\n" + "=".repeat(80));
  console.log("📈 Overall Summary");
  console.log("=".repeat(80));
  
  const totalRuns = logs.length;
  const totalTimeouts = logs.filter(log => log.timed_out).length;
  const totalErrors = logs.filter(log => log.exit_code !== 0 && !log.timed_out).length;
  const totalSuccess = logs.filter(log => log.exit_code === 0 && !log.timed_out).length;
  
  const durations = logs.map(log => log.duration_ms);
  const avgDuration = (durations.reduce((a, b) => a + b, 0) / durations.length / 1000).toFixed(1);
  
  const uniqueModels = new Set(logs.map(log => log.model)).size;
  
  console.log(`\nTotal runs: ${totalRuns}`);
  console.log(`Unique models: ${uniqueModels}`);
  console.log(`Success: ${totalSuccess} (${(totalSuccess / totalRuns * 100).toFixed(1)}%)`);
  console.log(`Timeouts: ${totalTimeouts} (${(totalTimeouts / totalRuns * 100).toFixed(1)}%)`);
  console.log(`Errors: ${totalErrors} (${(totalErrors / totalRuns * 100).toFixed(1)}%)`);
  console.log(`Average duration: ${avgDuration}s`);
  console.log(`\nLog file: ${LOG_FILE}`);
}

// Main execution
function main() {
  console.log("\n🔍 Ollama MCP Run Log Analysis");
  
  const logs = loadLogs();
  
  if (logs.length === 0) {
    console.log("\nNo runs logged yet. Run some Ollama MCP commands first!");
    process.exit(0);
  }

  showSummary(logs);
  analyzeByModel(logs);
  analyzeBatches(logs);
  showRecentRuns(logs);
  
  console.log("\n" + "=".repeat(80) + "\n");
}

main();
