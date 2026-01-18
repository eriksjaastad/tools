# Debug Log: Anti-Gravity File Watcher Hooks

**Date:** 2026-01-17
**Status:** UNRESOLVED - Paused (frustrated, need fresh eyes tomorrow)
**Version:** Anti-Gravity 1.4.2

---

## Goal

Have the Floor Manager automatically pick up task files when Super Manager drops them in `_handoff/`.

---

## Key Discovery (End of Session)

**Rules and Workflows are NOT file watchers.**

After researching actual Anti-Gravity documentation and video tutorials:
- **Rules** = System instructions applied during agent generation (like CLAUDE.md)
- **Workflows** = Manual `/` command triggers (like saved prompts)

Neither reacts to external file system changes. The `onFileCreate` trigger mentioned earlier was likely hallucinated by the AI Erik was consulting. Anti-Gravity doesn't have built-in file watching that triggers agent actions.

**This feature doesn't exist the way we thought it did.**

---

## What We Tried

### Attempt 1: JSON hooks file
- Created `agent_hooks.json` in project root
- Used `onFileCreate` trigger with pattern `_handoff/TASK_*.md`
- **Result:** Nothing happened

### Attempt 2: Markdown rules (1.4.2 syntax)
- Created `.agent/rules/floor-manager-task-pickup.md`
- Used `activation: always` frontmatter (later changed to `trigger: always_on`)
- Watched for files in `./_handoff/` matching `TASK_*.md`
- **Result:** Nothing in Inbox, no trigger

### Attempt 3: Fresh file with new name
- Deleted old task files
- Restarted Anti-Gravity
- Dropped `TASK_VERSION_HEADER_001.md` (brand new filename)
- **Result:** Still nothing

---

## Observations

- Files in `_handoff/drafts/` show as new in UI
- Files in `_handoff/` root don't show as new (gitignore sandwich? .gitkeep issue?)
- Inbox shows old "dependency pinning task" from earlier but no new triggers
- Gemini web was not helpful debugging its own IDE

---

## Files Created

```
agent-hub/
├── agent_hooks.json                     # JSON format (may be wrong for 1.4.2)
├── .agent/rules/floor-manager-task-pickup.md  # Markdown format
├── .cursor/hooks.json                   # Cursor hooks (untested)
└── .cursor/hooks/floor_manager_pickup.sh
```

---

## Possible Next Steps

1. **Check Anti-Gravity docs directly** - Find official 1.4.2 documentation for Workspace Rules
2. **Test simpler trigger** - Try watching a different directory that's not gitignored
3. **Check if .gitignore affects file watching** - The `_handoff/` directory has gitignore patterns
4. **Try the Cursor hooks** - Test if Cursor's hook system works as documented
5. **Ask in Anti-Gravity Discord/community** - Someone else has probably solved this
6. **Manual workaround** - Floor Manager polls `_handoff/` every N seconds instead of event-driven

---

## The Dream Architecture

```
Super Manager writes TASK_*.md to _handoff/
            │
            ▼
??? Something detects new file ???
            │
            ▼
Floor Manager receives trigger message
            │
            ▼
Floor Manager executes task autonomously
```

---

## Current Workaround

Manually tell Floor Manager: "Check `_handoff/` for pending tasks and execute them."

Not ideal, but functional.

---

## TOMORROW: Things to Try

### Research Needed
- [ ] Find official Anti-Gravity 1.4.2 documentation (not AI-generated guesses)
- [ ] Search Anti-Gravity Discord/community for "file watcher" or "auto trigger"
- [ ] Check if there's an MCP integration that could notify the agent
- [ ] Look for VS Code extension that watches files and sends to terminal/chat

### Possible Approaches
- [ ] **External watcher + clipboard hack** - `fswatch` detects file, copies message to clipboard, somehow pastes into Anti-Gravity?
- [ ] **Polling workflow** - Create `/check-tasks` workflow, Floor Manager runs it periodically
- [ ] **MCP notification** - Can our MCP server send a notification that Anti-Gravity displays?
- [ ] **VS Code task runner** - Since it's a VS Code fork, maybe tasks.json can watch and run something?
- [ ] **Just accept manual trigger** - Maybe the answer is "tell FM to check" and that's fine

### Questions to Answer
- [ ] Does Anti-Gravity have any notification/alert system we can hook into?
- [ ] Can we send keystrokes to Anti-Gravity from an external script?
- [ ] Is there an Anti-Gravity API or extension point we're missing?
- [ ] What do other people do for this use case?

---

## Knowledge Gathered

See `/Users/eriksjaastad/projects/__Knowledge/antigravity/` for:
- README.md (consolidated knowledge base)
- Video transcripts and analysis
- Perplexity research
- Comparison with Cursor

---

## Session Notes

- Started trying to test V4 pipeline handoff automation
- Discovered hooks don't work the way we were told
- Tried: JSON hooks, Markdown rules, different directories, fresh files
- Nothing triggered in Inbox
- Erik is frustrated (rightfully so) - pausing for tonight
- Will resume tomorrow with fresh research

---

*Documented by Claude Opus 4.5 - 2026-01-17 ~11pm Eastern*
*Session ended with frustration but good documentation for tomorrow*
