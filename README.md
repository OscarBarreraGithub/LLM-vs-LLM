# Claude Code Playground

A reference implementation showing how to configure Claude Code for maximum productivity. This repo demonstrates **custom agents, slash commands, skills, and a self-critical uncertainty workflow**.

The actual project is an AI Debate Tool that makes ChatGPT and Gemini debate each other via browser automation - but the real value here is seeing how the Claude Code configuration is structured.

## Claude Code Setup

### File Structure

```
CLAUDE.md                    # Project context - Claude reads this first

.claude/
├── settings.json            # Permissions and environment
├── agents/                  # Custom subagents
│   ├── code-reviewer.md     # Reviews code with certainty scores
│   ├── uncertainty-handler.md   # Creates GitHub issues when stuck
│   └── debate-expert.md     # Browser automation specialist
├── commands/                # Slash commands
│   ├── certainty.md         # /certainty - Assess confidence
│   ├── issue.md             # /issue - Create GitHub issue
│   └── debate.md            # /debate - Tool management
├── skills/                  # Auto-discovered capabilities
│   ├── uncertainty-assessment/
│   └── github-issue-creator/
└── rules/                   # Path-specific guidelines
    ├── python.md
    ├── browser-automation.md
    └── flask.md
```

### The Certainty Score Workflow

The key innovation: **Claude self-assesses confidence after making changes**.

| Score | Meaning | Action |
|-------|---------|--------|
| 9-10 | High confidence | Proceed normally |
| 7-8 | Confident | Note any minor unknowns |
| 5-6 | Moderate | Flag uncertainties explicitly |
| 3-4 | Low | Recommend human review |
| 1-2 | Very uncertain | Create GitHub issue, don't proceed |

This prevents Claude from making changes it's unsure about. Instead, it creates a GitHub issue explaining what's uncertain and asks for input.

### Custom Commands

| Command | Purpose |
|---------|---------|
| `/certainty` | Review recent changes and assess confidence levels |
| `/issue [description]` | Create a GitHub issue for uncertain areas |
| `/debate start\|stop\|status` | Manage the debate tool |

### Custom Agents

- **code-reviewer** - Reviews changes with risk assessment and certainty scores
- **uncertainty-handler** - Formats and creates GitHub issues when Claude is stuck
- **debate-expert** - Deep knowledge of Chrome DevTools Protocol and browser automation

### Using This as a Template

1. Fork/copy this repo
2. Edit `CLAUDE.md` with your project's context
3. Modify `.claude/rules/` for your tech stack
4. Customize agents and commands for your workflow

---

## The AI Debate Tool

This repo's actual project: browser automation that makes ChatGPT and Gemini debate each other.

### Quick Start

```bash
./run.sh              # Web UI at localhost:5050
./run.sh --cli        # Terminal interface
```

### How It Works

1. Chrome runs with `--remote-debugging-port=9222`
2. Tool connects via Chrome DevTools Protocol (CDP)
3. JavaScript injected to control both AI chat interfaces
4. Your existing logins are preserved - no API keys needed

### Features

- Live conversation view with both AI responses
- Configurable debate rounds and topics
- Custom prompts per AI
- LaTeX export for academic use
- Pause/resume debates anytime

For detailed usage, CLI commands, and troubleshooting, see [docs/USAGE.md](docs/USAGE.md).
