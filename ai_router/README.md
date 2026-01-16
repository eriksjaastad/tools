# AI Router

**Cost-optimized routing between local Ollama and cloud AI models**

Automatically routes AI requests to the most cost-effective model based on complexity, with automatic escalation when models fail or produce poor responses.

## Features

- 🆓 **Local-first**: Routes simple tasks to free Ollama models
- 💰 **Cost-aware**: Uses cheap cloud models (gpt-4o-mini) for medium tasks
- 🎯 **Quality fallback**: Escalates to expensive models (gpt-4o) when needed
- 🔄 **Auto-escalation**: Detects failures and poor responses, upgrades automatically
- 📊 **Telemetry**: Returns duration, model used, provider for cost tracking

## Project Structure

```text
ai_router/
├── 00_Index_ai-router.md      # Project index
├── AGENTS.md                  # Source of truth for AI
├── CLAUDE.md                  # AI collaboration instructions
├── TODO.md                    # Task tracking
├── router.py                  # Core routing logic
├── scripts/                   # Executable tools and tests
│   ├── test_gauntlet.py
│   ├── examples.py
│   └── ...
├── data/                      # Persistent data
│   └── logs/                  # Telemetry logs
└── Documents/                 # Documentation
```

## Quick Start

```python
from _tools.ai_router import AIRouter

# Initialize router
router = AIRouter()

# Auto-routing (recommended)
result = router.chat([
    {"role": "user", "content": "Is this email spam?"}
])

print(f"{result.model}: {result.text}")
# Output: llama3.2:3b: Yes, that appears to be spam.
```

## Usage Patterns

### 1. Auto-routing (Recommended)

Let the router decide based on complexity:

```python
router = AIRouter()

# Simple task → local (FREE)
result = router.chat([
    {"role": "user", "content": "Summarize: The meeting is at 3pm"}
])
# Uses: llama3.2:3b (local)

# Complex task → expensive
result = router.chat([
    {"role": "user", "content": "Design a scalable microservices architecture..."}
])
# Uses: gpt-4o (cloud)
```

### 2. Force Specific Tier

Override auto-routing:

```python
# Force local (save money, accept lower quality)
result = router.chat(messages, tier="local")

# Force cheap cloud
result = router.chat(messages, tier="cheap")

# Force expensive cloud
result = router.chat(messages, tier="expensive")
```

### 3. Override Model

Use a specific model:

```python
# Use specific local model
result = router.chat(messages, model_override="llama3.2:3b")

# Use specific cloud model
result = router.chat(messages, model_override="gpt-4o")
```

### 4. Disable Escalation

Prevent automatic upgrades:

```python
# Stay on local even if response is poor
result = router.chat(messages, tier="local", escalate=False)

### 5. Strict Mode (Loud Failures)

If you want the router to raise an exception instead of returning an error result (e.g., to prevent silent failures in automated pipelines):

```python
from _tools.ai_router import AIModelError

try:
    result = router.chat(messages, strict=True)
except AIModelError as e:
    print(f"Project crashed loudly: {e}")
```

## Routing Logic

### Complexity Heuristics

**→ Expensive (gpt-4o):**
- Keywords: "architecture", "refactor", "design doc", "security", etc.
- Contains code blocks (```)
- Very long prompts (>4000 chars)

**→ Cheap (gpt-4o-mini):**
- Medium length (>1200 chars)
- Contains questions

**→ Local (llama3.2:3b):**
- Short, simple tasks
- Classification/filtering
- Yes/no questions

### Escalation Logic

Automatically upgrades if:
- Model returns an error
- Response times out
- Response is too short (<40 chars)
- Response looks like a refusal

**Escalation chain:**
```
local (FREE) → cheap ($0.15/1M) → expensive ($2.50/1M)
```

## Result Object

```python
@dataclass
class AIResult:
    text: str              # Model's response
    provider: str          # "local" or "openai"
    model: str             # Actual model used
    tier: str              # "local", "cheap", or "expensive"
    duration_ms: int       # How long it took
    timed_out: bool        # Whether it timed out
    error: Optional[str]   # Error message if failed
```

## Telemetry & Performance Tracking

The router automatically logs every call to `logs/telemetry.jsonl` to track cost and performance.

### View Performance Summary

You can check for performance ceilings (slow models, errors, or timeouts) directly:

```python
from _tools.ai_router import AIRouter

router = AIRouter()
print(router.get_performance_summary())
```

**Output Example:**
```text
--- AI Router Performance Summary ---
LOCAL: 15 calls, avg 1200ms, max 4500ms, errors 0
OPENAI: 2 calls, avg 800ms, max 1200ms, errors 0

Performance Ceilings Hit:
Slow/Failed call: llama3.2:3b (4500ms) at 2026-01-05T08:30:42Z
```

## Configuration

### Custom Models

```python
router = AIRouter(
    local_model="qwen2.5:7b",       # Different local model
    cheap_model="gpt-4o-mini",
    expensive_model="gpt-4o",
)
```

### Custom Timeouts

```python
router = AIRouter(
    local_timeout_s=30.0,   # Faster local timeout
    cloud_timeout_s=120.0,  # Longer cloud timeout
)
```

### Custom Ollama Endpoint

```python
router = AIRouter(
    local_base_url="http://192.168.1.100:11434/v1",  # Remote Ollama
    local_api_key="ollama",
)
```

## Project Integration Examples

### Actionable AI Intel (Filtering)

```python
from _tools.ai_router import AIRouter

router = AIRouter()

def is_actionable(article: str) -> bool:
    """Filter articles using local model (FREE)"""
    result = router.chat(
        [{"role": "user", "content": f"Is this actionable? {article}"}],
        tier="local",  # Force local for speed/cost
        escalate=False  # Don't upgrade, good enough
    )
    return "yes" in result.text.lower()
```

### Cortana (Mixed Complexity)

```python
from _tools.ai_router import AIRouter

router = AIRouter()

def cortana_respond(user_input: str) -> str:
    """Auto-route based on query complexity"""
    result = router.chat([
        {"role": "system", "content": "You are Cortana, a helpful assistant."},
        {"role": "user", "content": user_input}
    ])
    # Simple queries → local (FREE)
    # Complex queries → cloud ($$)
    return result.text
```

### Trading Alerts (Spam Filter)

```python
from _tools.ai_router import AIRouter

router = AIRouter()

def is_useful_alert(alert: str) -> bool:
    """Filter trading alerts using local model"""
    result = router.chat(
        [{"role": "user", "content": f"Is this trading alert useful? {alert}"}],
        tier="local"
    )
    return "yes" in result.text.lower()
```

## Cost Tracking

Track usage across projects:

```python
from _tools.ai_router import AIRouter
import json

router = AIRouter()

# Track all calls
calls = []

for task in tasks:
    result = router.chat(task)
    calls.append({
        "provider": result.provider,
        "model": result.model,
        "tier": result.tier,
        "duration_ms": result.duration_ms,
        "chars": len(result.text)
    })

# Analyze
local_calls = sum(1 for c in calls if c["provider"] == "local")
cloud_calls = sum(1 for c in calls if c["provider"] == "openai")

print(f"Local: {local_calls} (FREE)")
print(f"Cloud: {cloud_calls} ($$)")
print(f"Savings: ${cloud_calls * 0.001:.2f} avoided by using local")
```

## Comparison with Direct OpenAI Usage

### Before (All Cloud)

```python
import openai

# Every call costs money
response = openai.ChatCompletion.create(
    model="gpt-4o-mini",
    messages=[...]
)
# Cost: $0.15 per 1M input tokens
```

### After (Smart Routing)

```python
from _tools.ai_router import AIRouter

router = AIRouter()

# Simple tasks use local (FREE)
result = router.chat(messages)
# Cost: $0 for local, $0.15/1M for cheap, $2.50/1M for expensive
```

**Estimated savings: 50-80% on typical workloads**

## Troubleshooting

### "Connection refused" (Local)

Ollama not running:
```bash
ollama serve &
# or
brew services start ollama
```

### "No API key" (Cloud)

Set environment variable:
```bash
export OPENAI_API_KEY="sk-..."
```

### Import Error

Add to PYTHONPATH:
```bash
export PYTHONPATH="[USER_HOME]/projects:$PYTHONPATH"
```

Or add to your shell profile:
```bash
echo 'export PYTHONPATH="[USER_HOME]/projects:$PYTHONPATH"' >> ~/.zshrc
source ~/.zshrc
```

## Tool Support (NEW in v1.1.0)

The AI Router now supports **agentic workflows** with Claude's Tool Runner pattern!

### Quick Start with Tools

```python
from _tools.ai_router import ToolRouter, tool

# Define a tool using the decorator
@tool("calculate")
def calculate(expression: str) -> dict:
    """Safely evaluate a mathematical expression."""
    result = eval(expression)  # (use safe eval in production!)
    return {"expression": expression, "result": result}

@tool("get_time")
def get_time() -> dict:
    """Get the current time."""
    from datetime import datetime
    return {"time": datetime.now().isoformat()}

# Create tool router
router = ToolRouter(
    tools=[calculate, get_time],
    max_turns=5,
    verbose=True,
)

# Run agentic task
result = router.run("What is 25 * 4? Also, what time is it?")
print(result.text)
# Claude will call both tools and provide a combined answer
```

### Tool Definition Best Practices

```python
@tool("search_files")
def search_files(
    query: str,
    directory: str = ".",
    file_type: str = "*"
) -> list[str]:
    """
    Search for files matching a pattern.
    
    Use this when the user wants to find specific files.
    Returns a list of matching file paths.
    
    Args:
        query: Pattern to search for in file names
        directory: Root directory to search from
        file_type: File extension filter (e.g., "py", "md")
    """
    from pathlib import Path
    return list(Path(directory).glob(f"**/*{query}*.{file_type}"))
```

### AgentResult Object

```python
@dataclass
class AgentResult:
    text: str              # Final response from Claude
    tool_calls: list       # All tools that were executed
    turns: int             # Number of conversation turns
    total_duration_ms: int # Total time taken
    model: str             # Model used
    stop_reason: str       # Why the conversation ended
```

### Documentation

- **Skill:** `agent-skills-library/claude-skills/tool-runner-patterns/`
- **Playbook:** `agent-skills-library/playbooks/tool-runner-patterns/`
- **Test:** `scripts/test_tool_runner.py`

## Future Enhancements

- [x] ~~**Multi-provider**: Support Anthropic, Gemini, etc.~~ ✅ Done!
- [x] ~~**Tool support**: Claude Tool Runner integration~~ ✅ Done!
- [ ] **Learned routing**: Train on telemetry data for better routing decisions
- [ ] **Judge model**: Use a small model to evaluate response quality
- [ ] **Cost tracking**: Built-in logger for cost analysis
- [ ] **Response caching**: Cache identical prompts
- [ ] **Streaming support**: Stream responses from both local and cloud

## Philosophy

This follows the **"local-first, cloud-fallback"** pattern from your LOCAL_AI_GAMEPLAN:

1. **Try local first** (free, fast, private)
2. **Escalate to cheap** if local fails
3. **Escalate to expensive** if quality matters

**Result:** Maximum cost savings with quality guarantees.

---

Part of the `_tools/` builder utilities collection.


## Related Documentation

- [[DOPPLER_SECRETS_MANAGEMENT]] - secrets management
- [[LOCAL_MODEL_LEARNINGS]] - local AI
- [[PROJECT_STRUCTURE_STANDARDS]] - project structure

- [[api_design_patterns]] - API design
- [[architecture_patterns]] - architecture
- [[cost_management]] - cost management
- [[prompt_engineering_guide]] - prompt engineering


- [[DOPPLER_SECRETS_MANAGEMENT]] - secrets management
- [[LOCAL_MODEL_LEARNINGS]] - local AI
- [[PROJECT_STRUCTURE_STANDARDS]] - project structure

- [[ai_model_comparison]] - AI models
- [[case_studies]] - examples
- [[cortana_architecture]] - Cortana AI
- [[performance_optimization]] - performance
- [[portfolio_content]] - portfolio/career
- [[security_patterns]] - security


- [[DOPPLER_SECRETS_MANAGEMENT]] - secrets management
- [[LOCAL_MODEL_LEARNINGS]] - local AI
- [[PROJECT_STRUCTURE_STANDARDS]] - project structure

- [[api_design_patterns]] - API design
- [[architecture_patterns]] - architecture
- [[cost_management]] - cost management
- [[prompt_engineering_guide]] - prompt engineering


- [[DOPPLER_SECRETS_MANAGEMENT]] - secrets management
- [[LOCAL_MODEL_LEARNINGS]] - local AI
- [[PROJECT_STRUCTURE_STANDARDS]] - project structure

- [[cortana-personal-ai/README]] - Cortana AI


- [[DOPPLER_SECRETS_MANAGEMENT]] - secrets management
- [[LOCAL_MODEL_LEARNINGS]] - local AI
- [[PROJECT_STRUCTURE_STANDARDS]] - project structure

- [[api_design_patterns]] - API design
- [[architecture_patterns]] - architecture
- [[cost_management]] - cost management
- [[prompt_engineering_guide]] - prompt engineering


- [[DOPPLER_SECRETS_MANAGEMENT]] - secrets management
- [[LOCAL_MODEL_LEARNINGS]] - local AI
- [[PROJECT_STRUCTURE_STANDARDS]] - project structure

- [[ai_model_comparison]] - AI models
- [[case_studies]] - examples
- [[cortana_architecture]] - Cortana AI
- [[performance_optimization]] - performance
- [[portfolio_content]] - portfolio/career
- [[security_patterns]] - security


- [[DOPPLER_SECRETS_MANAGEMENT]] - secrets management
- [[LOCAL_MODEL_LEARNINGS]] - local AI
- [[PROJECT_STRUCTURE_STANDARDS]] - project structure

- [[api_design_patterns]] - API design
- [[architecture_patterns]] - architecture
- [[cost_management]] - cost management
- [[prompt_engineering_guide]] - prompt engineering


- [[DOPPLER_SECRETS_MANAGEMENT]] - secrets management
- [[LOCAL_MODEL_LEARNINGS]] - local AI
- [[PROJECT_STRUCTURE_STANDARDS]] - project structure

