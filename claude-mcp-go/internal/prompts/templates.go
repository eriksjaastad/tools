package prompts

const RESOLVE_CONFLICT_TEMPLATE = `
You are resolving a disagreement between the Floor Manager and the Judge in the Agent Hub pipeline.

## Task Contract

` + "```json" + `
{{CONTRACT_JSON}}
` + "```" + `

## Judge's Report

` + "```markdown" + `
{{JUDGE_REPORT}}
` + "```" + `

## Floor Manager's Rebuttal

` + "```markdown" + `
{{REBUTTAL}}
` + "```" + `

## Your Task

1. Read both positions carefully
2. Consider the original requirements and acceptance criteria
3. Determine who is correct
4. Provide a clear recommendation

## Required Output

Respond with ONLY this JSON (no other text):

{
  "side": "floor_manager" or "judge",
  "reasoning": "Why this side is correct",
  "recommendation": "What action to take next"
}
`

const SECURITY_PROMPT_TEMPLATE = `
You are performing a security audit of the following files.

## Files to Review

{{FILES_CONTENT}}

## Security Checklist

Check for:
1. Hardcoded secrets (API keys, passwords, tokens)
2. SQL injection vulnerabilities
3. Command injection risks
4. XSS vulnerabilities
5. Path traversal attacks
6. Insecure deserialization
7. Missing input validation
8. Improper error handling that leaks info
9. Insecure cryptographic practices
10. Race conditions

## Required Output

Respond with ONLY this JSON (no other text):

{
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM|LOW",
      "file": "path/to/file",
      "line": 42,
      "description": "What the issue is",
      "recommendation": "How to fix it"
    }
  ]
}

If no issues found, return: {"findings": []}
`

const VALIDATE_PROMPT_TEMPLATE = `
You are validating a proposal for the Agent Hub pipeline.

## Proposal Content

` + "```markdown" + `
{{PROPOSAL_CONTENT}}
` + "```" + `

## Validation Checklist

Check if the proposal has:
1. Clear title
2. Target project specified
3. Complexity level (trivial/minor/major/critical)
4. Source files listed
5. Target output file specified
6. At least one requirement
7. At least one acceptance criterion
8. Constraints defined (allowed paths, forbidden paths)

## Required Output

Respond with ONLY this JSON (no other text):

{
  "valid": true/false,
  "issues": ["list of missing or unclear items"]
}
`
