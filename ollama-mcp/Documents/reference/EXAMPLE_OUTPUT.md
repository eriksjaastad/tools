# Example Log Output

## What ~/.ollama-mcp/runs.jsonl Looks Like

After running a few models, your log file will contain entries like this:

```jsonl
{"timestamp":"2025-12-31T18:30:15.234Z","model":"llama3.2:3b","start":"2025-12-31T18:30:15.234Z","end":"2025-12-31T18:30:28.451Z","duration_ms":13217,"exit_code":0,"output_chars":892,"timed_out":false}
{"timestamp":"2025-12-31T18:31:02.123Z","model":"qwen3:4b","start":"2025-12-31T18:31:02.123Z","end":"2025-12-31T18:31:14.890Z","duration_ms":12767,"exit_code":0,"output_chars":1453,"timed_out":false}
{"timestamp":"2025-12-31T18:32:45.678Z","model":"deepseek-r1:14b","start":"2025-12-31T18:32:45.678Z","end":"2025-12-31T18:34:45.678Z","duration_ms":120000,"exit_code":-1,"output_chars":5890,"timed_out":true}
{"timestamp":"2025-12-31T18:35:10.456Z","model":"llama3.2:3b","start":"2025-12-31T18:35:10.456Z","end":"2025-12-31T18:35:23.789Z","duration_ms":13333,"exit_code":0,"output_chars":1024,"timed_out":false,"batch_id":"lab9c8def","concurrency":2}
{"timestamp":"2025-12-31T18:35:10.789Z","model":"qwen3:14b","start":"2025-12-31T18:35:10.789Z","end":"2025-12-31T18:35:45.123Z","duration_ms":34334,"exit_code":0,"output_chars":3201,"timed_out":false,"batch_id":"lab9c8def","concurrency":2}
```

## Field Meanings

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `timestamp` | ISO 8601 | When the run started | `"2025-12-31T18:30:15.234Z"` |
| `model` | string | Model name | `"llama3.2:3b"` |
| `start` | ISO 8601 | Start time (same as timestamp) | `"2025-12-31T18:30:15.234Z"` |
| `end` | ISO 8601 | When the run finished | `"2025-12-31T18:30:28.451Z"` |
| `duration_ms` | number | How long it took (milliseconds) | `13217` (13.2 seconds) |
| `exit_code` | number | 0 = success, -1 = error/timeout | `0` |
| `output_chars` | number | Characters in stdout | `892` |
| `timed_out` | boolean | Did it exceed timeout? | `false` |
| `batch_id` | string? | Only for ollama_run_many | `"lab9c8def"` |
| `concurrency` | number? | Only for ollama_run_many | `2` |

## Example Analysis Output

After collecting the above logs, `node scripts/analyze-runs.js` would show:

```
🔍 Ollama MCP Run Log Analysis

================================================================================
📈 Overall Summary
================================================================================

Total runs: 5
Unique models: 4
Success: 4 (80.0%)
Timeouts: 1 (20.0%)
Errors: 0 (0.0%)
Average duration: 38.7s

Log file: /Users/eriksjaastad/.ollama-mcp/runs.jsonl

📊 Analysis by Model
================================================================================

🤖 llama3.2:3b
   Runs: 2
   Avg Duration: 13.3s (min: 13.2s, max: 13.3s)
   Avg Output: 958 chars
   Timeouts: 0/2 (0.0%)

🤖 qwen3:4b
   Runs: 1
   Avg Duration: 12.8s (min: 12.8s, max: 12.8s)
   Avg Output: 1453 chars
   Timeouts: 0/1 (0.0%)

🤖 qwen3:14b
   Runs: 1
   Avg Duration: 34.3s (min: 34.3s, max: 34.3s)
   Avg Output: 3201 chars
   Timeouts: 0/1 (0.0%)

🤖 deepseek-r1:14b
   Runs: 1
   Avg Duration: 120.0s (min: 120.0s, max: 120.0s)
   Avg Output: 5890 chars
   Timeouts: 1/1 (100.0%)


📦 Batch Analysis (ollama_run_many)
================================================================================

Total batches: 1

  Batch lab9c8def:
    Jobs: 2
    Concurrency: 2
    Models: llama3.2:3b, qwen3:14b
    Total wall time: 34.3s
    Avg job time: 23.8s


🕐 Recent Runs (last 5)
================================================================================

✅ qwen3:14b - 34.3s - 3201 chars [batch: lab9c8de]
   12/31/2025, 6:35:10 PM

✅ llama3.2:3b - 13.3s - 1024 chars [batch: lab9c8de]
   12/31/2025, 6:35:10 PM

⏱️ TIMEOUT deepseek-r1:14b - 120.0s - 5890 chars
   12/31/2025, 6:32:45 PM

✅ qwen3:4b - 12.8s - 1453 chars
   12/31/2025, 6:31:02 PM

✅ llama3.2:3b - 13.2s - 892 chars
   12/31/2025, 6:30:15 PM

================================================================================
```

## Insights You'd Get

From this sample data:

1. **Fastest Model**: `qwen3:4b` at 12.8s average
2. **Most Reliable**: `llama3.2:3b`, `qwen3:4b`, `qwen3:14b` (0% timeout)
3. **Problematic**: `deepseek-r1:14b` timed out (120s+)
4. **Most Verbose**: `deepseek-r1:14b` generated 5,890 chars
5. **Batch Efficiency**: 2 jobs ran in 34.3s (vs 47.6s sequential)

## Decision Making

Based on this data, you'd know:

- ✅ Use `qwen3:4b` for quick tasks (fast, reliable, good output)
- ✅ Use `llama3.2:3b` for standard tasks (reliable, moderate output)
- ✅ Use `qwen3:14b` for complex tasks (reliable but slower)
- ⚠️ Avoid `deepseek-r1:14b` or increase timeout to 180s+
- ✅ Concurrency of 2 saves time (34s vs 47s)

## After a Week

With 50-100 runs per model, you'll have:
- High-confidence averages
- Clear timeout patterns
- Model-specific performance profiles
- Data-driven model selection strategy

---

**This is what you'll see after your first few model runs!**

