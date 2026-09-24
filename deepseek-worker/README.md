# deepseek-worker

Shared DeepSeek coding-worker harness for Codex / Claude / Grok managers.

**Status:** Slice A / PR-1 implementation (pt #7569). Stub vertical path with filesystem job store.

| Doc | Purpose |
|---|---|
| [DESIGN.md](./DESIGN.md) | Architecture, state machine, CLI, storage, off-peak, notify, security |
| [PLAN.md](./PLAN.md) | Phased PR slices + acceptance map + first slice recommendation |
| [GAP_HOLOSCAPE_WRITEUP.md](./GAP_HOLOSCAPE_WRITEUP.md) | Missing Holoscape supervisor writeup |

## Installation

```bash
cd deepseek-worker
uv pip install -e .
# or
pip install -e .
```

## Usage

### Submit a work order

```bash
dsw submit --order fixtures/sample_order.yaml
# Outputs: <job_id>
```

### Check job status

```bash
dsw status <job_id>
```

### View job logs

```bash
dsw logs <job_id>
# Follow live logs:
dsw logs <job_id> --follow
```

### Cancel a job

```bash
dsw cancel <job_id>
```

### Check system health

```bash
dsw doctor
```

## Slice A Scope

This implementation provides:

1. **Package structure**: Python package with `dsw` console entry point
2. **Filesystem JobStore**: Jobs stored in `~/.deepseek-worker/` (configurable via `DSW_DATA_DIR`)
3. **Schemas**: Validated work order and handoff JSON structures
4. **CLI commands**: `submit`, `status`, `logs`, `cancel`, `doctor`
5. **Stub worker**: Brief subprocess that writes valid handoff (proves isolation + finalize)
6. **Idempotent submit**: Reuses existing job for same idempotency key
7. **Conflict detection**: One active job per pt_task_id and worktree_path
8. **Unit tests**: Schema validation and state transition tests

## Testing

```bash
cd deepseek-worker
pytest tests/ -v
```

## Example: End-to-End

```bash
# Submit work
JOB_ID=$(dsw submit --order fixtures/sample_order.yaml)
echo "Job ID: $JOB_ID"

# Wait a moment for stub worker to complete
sleep 3

# Check status
dsw status $JOB_ID

# Verify handoff exists
dsw status $JOB_ID --json | grep handoff_path
```

## Data Storage

By default, jobs are stored in `~/.deepseek-worker/`:

```
~/.deepseek-worker/
  jobs/
    <job_id>/
      job.json           # Job record
      work_order.json    # Input work order
      handoff.json       # Worker output (when complete)
      events.jsonl       # Event log
      worker.stdout.log  # Worker output
```

Override with `DSW_DATA_DIR` environment variable.

## Next Steps (Later Slices)

- **PR-2**: Off-peak enforcement, budget/timeout/retry caps
- **PR-3**: Crash recovery, notification queue
- **PR-4**: Manager entry points (agent-runtime-config skills)
- **PR-5**: Real DeepSeek worker integration
