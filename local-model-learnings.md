# Local Model Learnings
purpose: Operational knowledge for local Ollama models on Mac Mini
owner: OpenClaw (Mac Mini)
last_updated: 2026-03-10

## qwen3:32b

trigger: Need fast/cheap first-pass output (drafts, transforms, summaries, boilerplate)
rule: Use qwen3:32b first for low-risk generation; escalate only after a concrete quality failure.

trigger: Large rewrite request across many files
rule: Split into small, explicit chunks with file-by-file instructions and expected output format.

trigger: Output must be machine-consumable (JSON/YAML/table schema)
rule: Provide exact schema and one valid example in prompt; validate output before use.

trigger: Long prompts with mixed goals
rule: Keep prompts single-purpose. If needed, run sequential passes (analyze -> generate -> cleanup).

trigger: Model outputs plausible but uncertain technical claims
rule: Treat as draft reasoning only; verify against source files/tests before commit.

trigger: Time-sensitive command synthesis (CI, release, deploy)
rule: Ask model for command candidates, then run only after human/tool validation.

trigger: Test/code review drafting
rule: Good for first-pass review comments and bug hypotheses; require deterministic repro before action.

trigger: Prompt asks for architecture-level decisions
rule: Escalate to cloud model when tradeoff analysis spans many subsystems.

trigger: Prompt asks for nuanced policy/safety interpretation
rule: Escalate to stronger cloud model if ambiguity remains after first pass.

trigger: Prompt asks for final user-facing messaging in high-stakes context
rule: Use qwen for draft variants only; final text should be reviewed/refined in orchestrator model.

banned: Blindly trust generated commands touching secrets, auth, infra, or destructive file ops.
banned: Commit model-generated code without tests or local verification.
banned: Use qwen as sole reviewer for security-sensitive changes.

## Other local models (when added)

trigger: New Ollama model is installed
rule: Add one benchmark note here after 3+ real tasks (latency, pass/fail pattern, escalation threshold).

trigger: Repeated failure pattern appears 2+ times
rule: Add a new banned: or rule: entry immediately to prevent recurrence.

## Escalation checklist

trigger: Unsure whether to escalate from local model
rule: Escalate if any of the following are true:
- Fails schema/format twice
- Produces contradictory answers in same context
- Requires deep cross-file reasoning with strict correctness
- Involves security/auth/compliance decisions
