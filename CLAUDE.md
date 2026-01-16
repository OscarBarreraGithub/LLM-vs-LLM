# Claude Code Project Memory

This file helps Claude Code instances understand this project immediately.

## Project Overview

**AI Debate Tool** - A browser automation tool that orchestrates debates between ChatGPT and Gemini using Chrome DevTools Protocol. No API keys needed - uses your existing browser sessions.

## Architecture

```
┌─────────────────┐     ┌──────────────────┐
│   Web UI        │────▶│  Flask Server    │
│ (localhost:5050)│     │  (web_app.py)    │
└─────────────────┘     └────────┬─────────┘
                                 │
┌─────────────────┐              │
│   Terminal CLI  │──────────────┤
│   (debate.py)   │              │
└─────────────────┘              ▼
                        ┌──────────────────┐
                        │  Chrome DevTools │
                        │  Protocol (CDP)  │
                        └────────┬─────────┘
                                 │
                    ┌────────────┴────────────┐
                    ▼                         ▼
            ┌─────────────┐           ┌─────────────┐
            │  ChatGPT    │           │   Gemini    │
            │  (browser)  │           │  (browser)  │
            └─────────────┘           └─────────────┘
```

### Key Files

| File | Purpose |
|------|---------|
| `web_app.py` | Flask server (917 lines) - HTTP API, state management, debate loop |
| `debate.py` | Terminal CLI (712 lines) - async interface, interactive commands |
| `run.sh` | Launcher - starts Chrome with debugging + web server |
| `templates/index.html` | Web UI - prompt editor, conversation viewer, controls |
| `configs/default.json` | Default debate configuration template |

### Core Classes

- **ChromeController** (`web_app.py:59`) - Synchronous CDP communication
- **ChromeTab** (`debate.py:70`) - Async CDP connection
- **ChatGPT/Gemini classes** - AI-specific DOM selectors and interaction logic

## Common Commands

```bash
# Run the app (web interface)
./run.sh

# Run terminal CLI
./run.sh --cli

# Or directly
python3 web_app.py      # Web at localhost:5050
python3 debate.py       # Terminal mode

# Install dependencies
pip install websockets requests flask websocket-client
```

## Tech Stack

- **Python 3** with Flask, asyncio, websockets
- **Chrome DevTools Protocol** for browser automation
- **KaTeX** for math rendering in UI
- **LaTeX** for conversation export

## Code Conventions

@.claude/rules/python.md
@.claude/rules/browser-automation.md

## Certainty Score Protocol

**This project uses a self-critical workflow.** After making changes:

1. **Assess confidence** (1-10 scale):
   - 9-10: Highly confident, tested similar patterns
   - 7-8: Confident, straightforward change
   - 5-6: Moderate confidence, some unknowns
   - 3-4: Low confidence, unfamiliar territory
   - 1-2: Very uncertain, needs human review

2. **Report uncertainty**: For scores < 7, explicitly state what's uncertain

3. **Create GitHub issue**: For scores < 5, offer to create an issue with:
   - What was attempted
   - Why uncertain
   - Specific questions for the maintainer

4. **Never break things**: If very uncertain, ask before making changes

## Important Notes

- The CDP selectors for ChatGPT/Gemini change frequently when those sites update
- Always test changes with `./run.sh` to verify browser automation still works
- The `conversations/` folder is gitignored - LaTeX exports go there
- Chrome must run with `--remote-debugging-port=9222`

## Getting Help

- See @README.md for user-facing documentation
- See @.claude/rules/ for detailed coding guidelines
- Browser automation patterns are in both `debate.py` and `web_app.py`
