---
name: github-issue-creator
description: Creates well-formatted GitHub issues when Claude needs human input. Use when uncertainty is high or decisions require human judgment.
allowed-tools: Bash(gh issue:*), Read
model: haiku
---

# GitHub Issue Creator Skill

Creates structured GitHub issues for uncertainty escalation.

## When to Use

- Certainty score < 5 on a change
- Architecture decisions needed
- Business logic questions
- Multiple valid approaches with no clear winner
- External knowledge required

## Issue Structure

### Title Format

```
[Category]: Brief description
```

Categories:
- `Uncertainty` - General uncertainty about approach
- `Decision` - Choice between options needed
- `Question` - Specific question for maintainer
- `Review` - Code needs human review

### Body Template

```markdown
## Summary

One sentence describing what needs human input.

## Context

What was Claude working on when this came up?

## The Uncertainty

Specific description of what's unclear or risky.

## What Claude Considered

| Option | Description | Pros | Cons |
|--------|-------------|------|------|
| A | ... | ... | ... |
| B | ... | ... | ... |

## Specific Questions

1. Question 1?
2. Question 2?

## Files Involved

- `path/to/file.py` - description
- `path/to/other.py` - description

## Suggested Resolution

What Claude recommends once the uncertainty is resolved.

---
*This issue was created by Claude Code's uncertainty handling system.*
*Certainty Score: X/10*
```

## Labels

Always apply:
- `claude-uncertainty`

Additionally as relevant:
- `needs-decision` - When choosing between options
- `needs-info` - When more context required
- `architecture` - For design questions
- `browser-automation` - For CDP/selector issues

## Command

```bash
gh issue create \
  --title "[Category]: Title" \
  --body "$(cat <<'EOF'
[Issue body here]
EOF
)" \
  --label "claude-uncertainty"
```
