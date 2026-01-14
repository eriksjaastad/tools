#!/usr/bin/env node

/**
 * Smoke test for ollama-mcp server
 * Tests all three tools: list_models, run, run_many
 */

import { spawn } from 'child_process';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const serverPath = join(__dirname, '..', 'dist', 'server.js');

console.log('🧪 Ollama MCP Server Smoke Test\n');

// Helper to send MCP request
function sendRequest(proc, request) {
  return new Promise((resolve, reject) => {
    let response = '';
    let timeoutHandle;

    const onData = (data) => {
      response += data.toString();
      
      // Try to parse JSON-RPC response
      const lines = response.split('\n').filter(line => line.trim());
      for (const line of lines) {
        try {
          const parsed = JSON.parse(line);
          if (parsed.id === request.id) {
            clearTimeout(timeoutHandle);
            proc.stdout.off('data', onData);
            resolve(parsed);
            return;
          }
        } catch (e) {
          // Not valid JSON yet, keep reading
        }
      }
    };

    proc.stdout.on('data', onData);

    timeoutHandle = setTimeout(() => {
      proc.stdout.off('data', onData);
      reject(new Error('Request timeout'));
    }, 30000);

    proc.stdin.write(JSON.stringify(request) + '\n');
  });
}

async function runTests() {
  // Start server
  console.log('Starting MCP server...');
  const proc = spawn('node', [serverPath], {
    stdio: ['pipe', 'pipe', 'inherit'],
  });

  try {
    // Wait for server to initialize
    await new Promise(resolve => setTimeout(resolve, 1000));

    // Test 1: Initialize
    console.log('\n📋 Test 1: Initialize server');
    const initResponse = await sendRequest(proc, {
      jsonrpc: '2.0',
      id: 1,
      method: 'initialize',
      params: {
        protocolVersion: '2024-11-05',
        capabilities: {},
        clientInfo: {
          name: 'smoke-test',
          version: '1.0.0',
        },
      },
    });
    console.log('✅ Server initialized:', initResponse.result?.serverInfo?.name);

    // Test 2: List tools
    console.log('\n📋 Test 2: List tools');
    const toolsResponse = await sendRequest(proc, {
      jsonrpc: '2.0',
      id: 2,
      method: 'tools/list',
      params: {},
    });
    console.log('✅ Available tools:', toolsResponse.result?.tools?.map(t => t.name).join(', '));

    // Test 3: List models
    console.log('\n📋 Test 3: List Ollama models');
    const listResponse = await sendRequest(proc, {
      jsonrpc: '2.0',
      id: 3,
      method: 'tools/call',
      params: {
        name: 'ollama_list_models',
        arguments: {},
      },
    });
    
    if (listResponse.error) {
      console.error('❌ Error:', listResponse.error);
    } else {
      const models = JSON.parse(listResponse.result?.content?.[0]?.text || '{}').models;
      console.log('✅ Found models:', models?.join(', ') || 'none');
      
      if (!models || models.length === 0) {
        console.log('\n⚠️  No models found. Install one with: ollama pull llama3.2');
        console.log('Skipping remaining tests that require models.\n');
        return;
      }

      // Test 4: Run single model (prefer smaller/faster models for testing)
      const preferredModels = ['llama3.2:3b', 'llama3.2', 'qwen2.5:3b'];
      const testModel = models.find(m => preferredModels.includes(m)) || models[0];
      console.log(`\n📋 Test 4: Run single model (${testModel})`);
      const runResponse = await sendRequest(proc, {
        jsonrpc: '2.0',
        id: 4,
        method: 'tools/call',
        params: {
          name: 'ollama_run',
          arguments: {
            model: testModel,
            prompt: 'Say "Hello from smoke test" and nothing else.',
          },
        },
      });

      if (runResponse.error) {
        console.error('❌ Error:', runResponse.error);
      } else {
        const result = JSON.parse(runResponse.result?.content?.[0]?.text || '{}');
        console.log('✅ Model response:', {
          exitCode: result.exitCode,
          outputLength: result.stdout?.length || 0,
          preview: result.stdout?.substring(0, 100).trim() || 'empty',
        });
      }

      // Test 5: Run many (2 jobs)
      if (models.length >= 1) {
        console.log(`\n📋 Test 5: Run many (2 jobs with ${testModel})`);
        const runManyResponse = await sendRequest(proc, {
          jsonrpc: '2.0',
          id: 5,
          method: 'tools/call',
          params: {
            name: 'ollama_run_many',
            arguments: {
              jobs: [
                {
                  model: testModel,
                  prompt: 'Count to 3.',
                },
                {
                  model: testModel,
                  prompt: 'Name one color.',
                },
              ],
              maxConcurrency: 2,
            },
          },
        });

        if (runManyResponse.error) {
          console.error('❌ Error:', runManyResponse.error);
        } else {
          const results = JSON.parse(runManyResponse.result?.content?.[0]?.text || '{}').results;
          console.log('✅ Completed jobs:', results?.length || 0);
          results?.forEach((r, i) => {
            console.log(`   Job ${i + 1}: exitCode=${r.exitCode}, output="${r.stdout?.substring(0, 50).trim()}..."`);
          });
        }
      }
    }

    console.log('\n✅ All tests completed!\n');

  } catch (error) {
    console.error('\n❌ Test failed:', error.message);
    process.exit(1);
  } finally {
    proc.kill();
  }
}

runTests().catch((error) => {
  console.error('Fatal error:', error);
  process.exit(1);
});

