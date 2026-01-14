# Floor Manager Task: Verify Response Quality Detection

**Model:** Floor Manager (verification task)
**Objective:** Verify isGoodResponse() function matches AI Router logic

---

## ⚠️ DOWNSTREAM HARM ESTIMATE

- **If this fails:** Bad responses accepted as good. Good responses rejected as bad. Unnecessary fallbacks or missed fallbacks.
- **Known pitfalls:** Min length too strict for classification. Refusal patterns incomplete.
- **Recovery:** Fix function, rebuild.

---

## 📚 LEARNINGS APPLIED

- [x] Ported from AI Router (`_tools/ai_router/router.py`)
- [x] Task-aware: classification/extraction allow short answers
- [x] Refusal detection: "I cannot", "I'm unable", etc.

---

## CONSTRAINTS (READ FIRST)

- DO NOT change the function signature
- DO NOT add task types not in the spec
- MATCH the AI Router behavior

---

## 🎯 [ACCEPTANCE CRITERIA]

### Function Exists
- [x] `isGoodResponse(text: string, taskType: string): boolean` exists
- [x] Function is called in the fallback loop

### Length Checks (Task-Aware)
- [x] Classification: accepts responses >= 1 character
- [x] Extraction: accepts responses >= 1 character
- [x] Code: requires responses >= 40 characters
- [x] Reasoning: requires responses >= 40 characters
- [x] File_mod: requires responses >= 40 characters
- [x] Auto: requires responses >= 40 characters (conservative default)

### Refusal Detection
- [x] Rejects responses containing "I cannot"
- [x] Rejects responses containing "I'm unable"
- [x] Rejects responses containing "I don't have access"
- [x] Case handling: check is case-insensitive OR covers common variants

### Edge Cases
- [x] Empty string returns false
- [x] Whitespace-only returns false
- [x] "YES" returns true for classification
- [x] "YES" returns false for code (too short)

### Verification Test
```javascript
// Quick manual test
function isGoodResponse(text, taskType) {
  // ... paste actual function here
}

console.log(isGoodResponse("YES", "classification")); // should be true
console.log(isGoodResponse("YES", "code")); // should be false
console.log(isGoodResponse("I cannot do that", "classification")); // should be false
console.log(isGoodResponse("", "classification")); // should be false
```

---

## FLOOR MANAGER PROTOCOL

1. Find `isGoodResponse()` in `src/server.ts`
2. Compare logic against each acceptance criterion
3. Test edge cases mentally or with quick node REPL
4. If any criterion fails, fix the function
5. Rebuild and verify
6. Mark all criteria with [x] when verified

---
