---
name: uncertainty-assessment
description: Automatically assesses confidence in code changes. Apply after making edits to evaluate certainty and flag risky areas. Use when Claude should self-critique changes.
allowed-tools: Read, Grep, Glob
model: haiku
---

# Uncertainty Assessment Skill

This skill enables self-critical evaluation of code changes.

## When This Applies

- After making code edits
- When reviewing proposed changes
- When asked about confidence in a solution

## Assessment Framework

### Certainty Factors

**Increases certainty (+)**:
- Well-understood pattern/library
- Similar code exists in codebase
- Clear requirements
- Straightforward logic
- Tests exist and pass

**Decreases certainty (-)**:
- Unfamiliar API/library
- Complex control flow
- Race conditions possible
- External dependencies
- No existing similar code
- Unclear requirements

### Scoring Guide

| Score | Description | Example |
|-------|-------------|---------|
| 10 | Trivial, obvious | Fixing a typo |
| 9 | Very confident | Simple refactor following existing pattern |
| 8 | Confident | New function using well-known libraries |
| 7 | Fairly confident | Integration with documented API |
| 6 | Moderate | New feature with some unknowns |
| 5 | Uncertain | Complex logic with edge cases |
| 4 | Low confidence | Unfamiliar domain |
| 3 | Very uncertain | Multiple interacting systems |
| 2 | Guessing | Unclear requirements |
| 1 | No confidence | Completely unfamiliar territory |

## Output

After assessing, report:

1. **Certainty score** (X/10)
2. **Key factors** affecting the score
3. **Specific uncertainties** if score < 7
4. **Recommendation** (proceed / review needed / create issue)
