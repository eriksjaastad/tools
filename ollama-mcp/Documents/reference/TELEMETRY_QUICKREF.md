# Ollama MCP Telemetry - Quick Reference

## 📁 Files Created
```
src/logger.ts              - JSON Lines logging utility
scripts/analyze-runs.js    - Performance analysis script
TELEMETRY_GUIDE.md         - Detailed walkthrough
~/.ollama-mcp/runs.jsonl   - Auto-created log file
```

## 🚀 Quick Start

### Run Models (via Cursor)
```
Use ollama_run with llama3.2 to [task]
```
→ Automatically logs to `~/.ollama-mcp/runs.jsonl`

### View Stats
```bash
node scripts/analyze-runs.js
```

## 📊 What Gets Logged

```json
{
  "timestamp": "2025-12-31T10:30:00Z",
  "model": "llama3.2:3b",
  "start": "2025-12-31T10:30:00Z",
  "end": "2025-12-31T10:30:15Z",
  "duration_ms": 15234,
  "exit_code": 0,
  "output_chars": 1250,
  "timed_out": false,
  "batch_id": "abc123",      // only for ollama_run_many
  "concurrency": 2           // only for ollama_run_many
}
```

**NOT logged:** Prompts (privacy), system info, tokens (not available)

## 📈 Analysis Output

```
📈 Overall Summary
────────────────────────────────────────
Total runs: 45
Success: 42 (93.3%)
Timeouts: 3 (6.7%)
Average duration: 28.4s

📊 Analysis by Model
────────────────────────────────────────
🤖 llama3.2:3b
   Runs: 20
   Avg Duration: 18.2s (min: 12.1s, max: 45.2s)
   Avg Output: 950 chars
   Timeouts: 1/20 (5%)

🤖 qwen3:4b
   Runs: 15
   Avg Duration: 12.3s (min: 8.4s, max: 20.1s)
   Avg Output: 1,420 chars
   Timeouts: 0/15 (0%)

📦 Batch Analysis
────────────────────────────────────────
Batch abc123:
  Jobs: 3
  Concurrency: 2
  Total wall time: 45.2s
  Avg job time: 32.1s
```

## 🎯 After 1 Week

You'll be able to answer:
- ✅ "Which model handles unit tests fastest?"
- ✅ "Does qwen3:4b timeout less than deepseek?"
- ✅ "What's the avg output size per model?"
- ✅ "Should I use concurrency=2 or 4?"

## 🔧 Testing Now

```bash
# 1. Restart Cursor to load new code

# 2. Run a test
# (In Cursor): "Use ollama_run with llama3.2 to say hello"

# 3. Check log
cat ~/.ollama-mcp/runs.jsonl

# 4. Analyze
node scripts/analyze-runs.js
```

## 💡 Pro Tips

- **No cleanup needed** - JSON Lines appends forever
- **Grep-friendly** - Each line is valid JSON
- **Privacy-safe** - No prompts stored
- **Zero overhead** - Async logging, doesn't slow runs
- **Cross-session** - Data persists across Cursor restarts

## 🛠️ Advanced Queries

```bash
# Count runs per model
cat ~/.ollama-mcp/runs.jsonl | jq -r '.model' | sort | uniq -c

# Find timeouts
cat ~/.ollama-mcp/runs.jsonl | jq 'select(.timed_out == true)'

# Average duration (all models)
cat ~/.ollama-mcp/runs.jsonl | jq '.duration_ms' | awk '{sum+=$1; n++} END {print sum/n/1000 "s"}'

# Models by success rate
cat ~/.ollama-mcp/runs.jsonl | jq -s 'group_by(.model) | map({model: .[0].model, success_rate: (map(select(.exit_code==0)) | length) / length * 100})'
```

## 🚨 Troubleshooting

**Log file doesn't exist?**
→ Run a model first, it creates on first use

**Permission denied?**
→ Check `~/.ollama-mcp/` directory permissions

**Analysis script crashes?**
→ Ensure valid JSON Lines (each line must be valid JSON)

**Too much data?**
→ Rotate manually: `mv runs.jsonl runs-archive-$(date +%Y%m).jsonl`

---

**Status:** ✅ Feature Complete & Ready to Use  
**Next:** Use models, collect data, analyze after 1 week

