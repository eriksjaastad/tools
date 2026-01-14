#!/usr/bin/env node
/**
 * Updates the last_review date in config/routing.yaml to today's date.
 */
import { readFileSync, writeFileSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import yaml from 'js-yaml';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const CONFIG_PATH = join(__dirname, '..', 'config', 'routing.yaml');

try {
  const fileContents = readFileSync(CONFIG_PATH, 'utf8');
  const config = yaml.load(fileContents);

  if (!config || typeof config !== 'object') {
    throw new Error('Invalid config file');
  }

  const today = new Date().toISOString().split('T')[0];
  
  if (!config.telemetry_review) {
    config.telemetry_review = {};
  }
  
  config.telemetry_review.last_review = today;

  const newYaml = yaml.dump(config, { indent: 2 });
  writeFileSync(CONFIG_PATH, newYaml, 'utf8');

  console.log(`✅ Telemetry review marked as complete for: ${today}`);
  console.log(`Updated last_review in ${CONFIG_PATH}`);
} catch (error) {
  console.error('❌ Failed to update telemetry review date:', error.message);
  process.exit(1);
}
