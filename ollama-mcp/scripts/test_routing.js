#!/usr/bin/env node

/**
 * Test script for Smart Local Routing
 */

import { spawn } from 'child_process';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const serverPath = join(__dirname, '..', 'dist', 'server.js');

console.log('🧪 Testing Ollama MCP Smart Local Routing\n');

function sendRequest(proc, request) {
  return new Promise((resolve, reject) => {
    let response = '';
    const onData = (data) => {
      response += data.toString();
      const lines = response.split('\n').filter(line => line.trim());
      for (const line of lines) {
        try {
          const parsed = JSON.parse(line);
          if (parsed.id === request.id) {
            proc.stdout.off('data', onData);
            resolve(parsed);
            return;
          }
        } catch (e) {}
      }
    };
    proc.stdout.on('data', onData);
    proc.stdin.write(JSON.stringify(request) + '\n');
  });
}

async function runTests() {
  const proc = spawn('node', [serverPath], { stdio: ['pipe', 'pipe', 'inherit'] });
  
  try {
    await new Promise(resolve => setTimeout(resolve, 1000));

    // Initialize
    await sendRequest(proc, {
      jsonrpc: '2.0', id: 1, method: 'initialize',
      params: { protocolVersion: '2024-11-05', capabilities: {}, clientInfo: { name: 'test', version: '1.0' } }
    });

    // Test 1: Classification (should route to llama3.2:3b)
    console.log('📋 Test 1: Smart routing for "classification"');
    const resp1 = await sendRequest(proc, {
      jsonrpc: '2.0', id: 2, method: 'tools/call',
      params: {
        name: 'ollama_run',
        arguments: {
          task_type: 'classification',
          prompt: 'Is 2+2=4? Answer only YES or NO.'
        }
      }
    });
    
    const result1 = JSON.parse(resp1.result.content[0].text);
    console.log(`   Model used: ${result1.metadata.model_used}`);
    console.log(`   Models tried: ${result1.metadata.models_tried.join(', ')}`);
    console.log(`   Response: ${result1.stdout.trim()}`);

    // Test 2: Explicit model (should bypass routing)
    console.log('\n📋 Test 2: Explicit model bypass');
    const resp2 = await sendRequest(proc, {
      jsonrpc: '2.0', id: 3, method: 'tools/call',
      params: {
        name: 'ollama_run',
        arguments: {
          model: 'deepseek-r1:14b',
          prompt: 'Say "Bypass successful"'
        }
      }
    });
    const result2 = JSON.parse(resp2.result.content[0].text);
    console.log(`   Model used: ${result2.metadata.model_used}`);
    console.log(`   Response: ${result2.stdout.trim()}`);

    console.log('\n✅ Smart Routing tests completed!');
  } catch (error) {
    console.error('\n❌ Test failed:', error);
  } finally {
    proc.kill();
  }
}

runTests();
