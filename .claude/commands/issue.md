---
description: Create a GitHub issue for uncertain areas or questions
allowed-tools: Read, Bash(gh issue:*), Bash(git:*)
argument-hint: [title or description of uncertainty]
---

# Create Uncertainty Issue

Create a GitHub issue to document uncertainty and request human input.

## Arguments

`$ARGUMENTS` - Brief description of the uncertainty (optional, will prompt if not provided)

## Process

1. **Gather context**:
   - What was being attempted?
   - What changes were made (if any)?
   - What is uncertain?

2. **Format the issue**:

```markdown
## Context

[What task was being worked on]

## Uncertainty

[Specific area of uncertainty]

## What Was Attempted

[Steps taken, approaches considered]

## Questions

1. [Specific question needing answer]
2. [Additional questions if any]

## Options Considered

| Option | Pros | Cons |
|--------|------|------|
| A | ... | ... |
| B | ... | ... |

## Impact

- Files affected: ...
- Risk if wrong: ...

---
*Created by Claude Code - certainty assessment flagged this area for human review*
```

3. **Create the issue**:

```bash
gh issue create \
  --title "Uncertainty: $ARGUMENTS" \
  --body "..." \
  --label "claude-uncertainty"
```

4. **Report back** with the issue URL
