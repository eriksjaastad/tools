# Model Shootout Benchmarks

Benchmark suite for evaluating local LLMs for the Floor Manager role in the Unified Agent System.

## Purpose
The Floor Manager needs to parse task specifications, route to appropriate workers, synthesize results, and make judgment calls. Gemini 2.0 Flash is the default Floor Manager, but local models can significantly reduce costs if they meet reliability thresholds.

## Requirements
- Python 3.10+
- Ollama running locally
- Project dependencies installed (`pip install -r requirements.txt`)

## Usage
Run the shootout against default models:
```bash
python -m benchmarks.model_shootout
```

Specify custom models:
```bash
python -m benchmarks.model_shootout --models llama3.2:1b,qwen2.5-coder:14b
```

## Test Cases
1. **task_parsing**: JSON extraction from task descriptions.
2. **routing_decision**: Categorizing tasks to worker types.
3. **judgment_call**: Resolving conflicts between worker outputs.
4. **synthesis**: Summarizing multi-worker progress.

## Interpreting Results
Results are saved to `shootout_results.json`. The output prints a success rate and average latency for each model.
- **Success Rate**: Ideally 100% for Floor Manager reliability.
- **Latency**: Lower is better, but secondary to accuracy for coordination tasks.
