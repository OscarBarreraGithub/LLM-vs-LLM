---
description: Two agents debate the best approach before any code is written
allowed-tools: Read, Grep, Glob, Task
argument-hint: <problem or feature to debate>
---

# Code Debate

Before implementing, have two agents argue different approaches to: **$ARGUMENTS**

## Process

Run a structured debate with 4 rounds + synthesis:

### Round 1: Advocate Proposes
Use the **advocate** agent to propose an initial approach.
- Read relevant code first to understand context
- Propose a concrete solution with benefits

### Round 2: Skeptic Critiques
Use the **skeptic** agent to critique the proposal.
- Acknowledge strengths
- Identify weaknesses and edge cases
- Propose an alternative

### Round 3: Advocate Responds
Advocate addresses the critique.
- Defend valid points
- Adapt to good feedback
- Find middle ground if appropriate

### Round 4: Skeptic Responds
Skeptic evaluates the defense.
- Concede points that were well-defended
- Press on remaining concerns
- Refine the alternative if needed

### Synthesis
Combine insights into a final recommendation:

```markdown
## Code Debate Summary: [Topic]

**Rounds**: 4
**Approaches Debated**:
1. [Advocate's approach]
2. [Skeptic's alternative]

**Key Insights**:
- [Insight from debate]
- [Insight from debate]

**Recommendation**: [Winning approach or hybrid]

**Confidence**: [X/10]

**Trade-offs accepted**:
- [Trade-off and why it's acceptable]

**Next steps**:
1. [Concrete action]
2. [Concrete action]
```

## After the Debate

Log the outcome to `.claude/certainty-log.jsonl`:

```json
{"timestamp": "...", "session": "code-debate", "score": X, "summary": "Debated [topic]: [recommendation]", "uncertainties": [...]}
```

## Example

```
/code-debate "How should we handle authentication in the API?"
```
