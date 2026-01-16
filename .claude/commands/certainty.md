---
description: Evaluate certainty of recent changes, flag areas needing review, and log to history
allowed-tools: Read, Grep, Glob, Bash(git:*), Edit
---

# Certainty Assessment

Review the recent changes in this session, provide a certainty assessment, and log it.

## Instructions

1. **Identify recent changes**: Use `git diff` and `git status` to see what's modified

2. **For each changed file**, assess:
   - What was the intent of the change?
   - Is the implementation correct?
   - Are there edge cases not handled?
   - Could this break existing functionality?

3. **Provide certainty scores** (1-10):
   - 9-10: Very confident - well-understood pattern, tested approach
   - 7-8: Confident - straightforward change, low risk
   - 5-6: Moderate - some unknowns, could use verification
   - 3-4: Low - unfamiliar territory, recommend review
   - 1-2: Very low - significant uncertainty, needs human input

4. **Output format**:

```
## Certainty Assessment

### Overall: [X/10]

### By File

| File | Change | Certainty | Notes |
|------|--------|-----------|-------|
| ... | ... | X/10 | ... |

### Areas of Uncertainty

1. **[Area]** (Certainty: X/10)
   - Why uncertain: ...
   - What could go wrong: ...
   - Recommendation: ...

### Recommended Actions

- [ ] ...
```

5. **If any certainty < 5**: Offer to create a GitHub issue with `/issue`

6. **Log the assessment** to `.claude/certainty-log.jsonl`:

```json
{"timestamp": "ISO-8601", "session": "brief-description", "score": X, "summary": "one-line summary of changes", "uncertainties": ["list", "if any"]}
```

Append one line per assessment. Keep summary under 100 chars.
