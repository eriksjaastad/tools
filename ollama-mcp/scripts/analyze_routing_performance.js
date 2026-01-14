#!/usr/bin/env node
/**
 * Analyzes telemetry data and provides routing recommendations.
 */
import { createReadStream, readFileSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import readline from 'readline';
import yaml from 'js-yaml';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const CONFIG_PATH = join(__dirname, '..', 'config', 'routing.yaml');
const LOG_FILE = join(process.env.HOME || '', '.ollama-mcp', 'runs.jsonl');

async function analyzePerformance() {
  try {
    const config = yaml.load(readFileSync(CONFIG_PATH, 'utf8'));
    const lastReviewDate = new Date(config.telemetry_review.last_review);
    
    console.log(`Analyzing telemetry since: ${lastReviewDate.toISOString().split('T')[0]}`);
    console.log(`Using thresholds: ${config.telemetry_review.review_interval_days} days, ${config.telemetry_review.min_runs_before_review} runs\n`);

    const stats = {}; // { task_type: { model: { total: 0, success: 0 } } }

    const fileStream = createReadStream(LOG_FILE);
    const rl = readline.createInterface({
      input: fileStream,
      crlfDelay: Infinity,
    });

    for await (const line of rl) {
      if (!line.trim()) continue;
      try {
        const run = JSON.parse(line);
        const runDate = new Date(run.timestamp);
        
        if (runDate < lastReviewDate) continue;

        const taskType = run.task_type || 'auto';
        const model = run.model;

        if (!stats[taskType]) stats[taskType] = {};
        if (!stats[taskType][model]) stats[taskType][model] = { total: 0, success: 0 };

        stats[taskType][model].total++;
        
        // Success criteria: exit_code 0, not timed_out
        // And we'll check output_chars as a proxy for quality if not classification
        const isClassification = taskType === 'classification' || taskType === 'extraction';
        const minChars = isClassification ? 1 : 40;
        
        if (run.exit_code === 0 && !run.timed_out && run.output_chars >= minChars) {
          stats[taskType][model].success++;
        }
      } catch (e) {
        // Skip malformed lines
      }
    }

    // Output results and recommendations
    const taskTypes = Object.keys(stats).sort();
    
    if (taskTypes.length === 0) {
      console.log('No telemetry data found since last review.');
      return;
    }

    for (const taskType of taskTypes) {
      console.log(`Task Type: ${taskType}`);
      const models = Object.keys(stats[taskType]).sort((a, b) => {
        const rateA = stats[taskType][a].success / stats[taskType][a].total;
        const rateB = stats[taskType][b].success / stats[taskType][b].total;
        return rateB - rateA;
      });

      let totalTaskRuns = 0;
      for (const model of models) {
        const { total, success } = stats[taskType][model];
        totalTaskRuns += total;
        const rate = ((success / total) * 100).toFixed(1);
        console.log(`  ${model.padEnd(20)} - ${success}/${total} runs (${rate}% success)`);
      }

      // Recommendation
      if (totalTaskRuns < 10) {
        console.log(`  Recommendation: Need more data (only ${totalTaskRuns} runs)`);
      } else {
        const currentChain = config.fallback_chains[taskType] || [];
        const recommendedChain = models.slice(0, 3); // Keep top 3
        
        const isSame = JSON.stringify(currentChain) === JSON.stringify(recommendedChain);
        
        if (isSame) {
          console.log(`  Recommendation: Chain order is optimal.`);
        } else {
          console.log(`  Recommendation: Update chain to: [${recommendedChain.join(', ')}]`);
        }
      }
      console.log('');
    }

    console.log('--------------------------------------------------');
    console.log('Instructions for Floor Manager:');
    console.log('1. Review the recommendations above.');
    console.log('2. If you want to apply changes, manually update config/routing.yaml.');
    console.log('3. Run "npm run build" if you change the config.');
    console.log('4. Run "node scripts/mark_telemetry_reviewed.js" to reset the timer.');

  } catch (error) {
    if (error.code === 'ENOENT') {
      console.log('No telemetry file found yet. Start using the MCP to generate data.');
    } else {
      console.error('Analysis failed:', error.message);
    }
  }
}

analyzePerformance();
