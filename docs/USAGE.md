# AI Debate Tool - Usage Guide

Detailed documentation for the AI Debate Tool.

## Setup

### Install Dependencies

```bash
pip install websockets requests flask websocket-client
```

### First-Time Login

The first time you run, log in to both services in the Chrome window:
- ChatGPT: https://chatgpt.com
- Gemini: https://gemini.google.com/app

Your login is saved in the debug profile (`/tmp/chrome-debug`).

## Web Interface

The web UI at `http://localhost:5050` provides:

| Feature | Description |
|---------|-------------|
| **Live Conversation** | See both AI responses in one scrollable view |
| **Start Debate** | Enter a topic and kick off the debate |
| **Run Rounds** | Run 1, 3, 5, or custom number of rounds |
| **Pause/Resume** | Stop the debate anytime, resume when ready |
| **Inject Prompt** | Send custom messages to either or both AIs |
| **New Chat** | Reset both conversations to start fresh |
| **Configure** | Set roles, instructions, and goals on the fly |

## Terminal Commands

If using `--cli` mode:

```
debate> start <topic>       # Start debate with topic
debate> round [n]           # Run n rounds (default: 1)
debate> chatgpt <msg>       # Send message to ChatGPT only
debate> gemini <msg>        # Send message to Gemini only
debate> inject <msg>        # Send message to both
debate> set <key> <value>   # Update configuration
debate> new                 # Reset both conversations
debate> status              # Show stats (rounds, char count)
debate> history             # View recent messages
debate> config              # Show current configuration
debate> help                # Show all commands
debate> quit                # Exit
```

## Configuration Options

| Key | Description | Example |
|-----|-------------|---------|
| `role_chatgpt` | ChatGPT's position in debate | "Argue for tabs over spaces" |
| `role_gemini` | Gemini's position in debate | "Argue for spaces over tabs" |
| `header_chatgpt` | Header prepended to ChatGPT prompts | "You are in a debate." |
| `header_gemini` | Header prepended to Gemini prompts | "You are in a debate." |
| `instructions` | Instructions appended to all prompts | "Be concise. Max 2 paragraphs." |
| `goal` | Convergence goal | "Find common ground" |
| `max_rounds` | Auto-pause after N rounds | 5 |
| `delay` | Seconds between messages | 3 |

### Setting Configuration

**Web UI:** Use the Configure panel

**CLI:**
```
debate> set role_chatgpt "Defend the Oxford comma"
debate> set role_gemini "Argue against the Oxford comma"
debate> set instructions "Keep responses under 200 words"
```

**Command line:**
```bash
python3 debate.py --role-chatgpt "Pro-tabs" --role-gemini "Pro-spaces"
```

## Example Sessions

### Philosophy Debate
```
debate> set role_chatgpt "Argue for determinism"
debate> set role_gemini "Argue for free will"
debate> set goal "Identify the core disagreement"
debate> start "Do humans have free will?"
debate> round 5
```

### Code Review
```
debate> set role_chatgpt "Find bugs and issues in this code"
debate> set role_gemini "Defend the code or suggest improvements"
debate> set instructions "Be specific. Reference line numbers."
debate> chatgpt "Review this Python function: def factorial(n): return 1 if n <= 1 else n * factorial(n-1)"
debate> round 3
```

### Convergence Discussion
```
debate> set goal "Reach a consensus on best practices"
debate> set instructions "Build on each other's points. Find agreement."
debate> start "What are the best practices for error handling in Python?"
debate> round 5
```

## Troubleshooting

### "Cannot connect to Chrome"

Chrome needs to run with remote debugging. The `run.sh` script handles this, but if running manually:

```bash
# Close Chrome completely first (Cmd+Q), then:
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222 \
  --remote-allow-origins=* \
  --user-data-dir="/tmp/chrome-debug"
```

### "ChatGPT/Gemini tab not found"

Make sure both tabs are open:
- https://chatgpt.com
- https://gemini.google.com/app

### Empty responses

The AI might still be generating. The tool waits up to 2 minutes, but very long responses might timeout. Try:
- Using `set instructions "Keep responses brief"`
- Checking the browser to see if there's an error

### Context getting too long

When conversations get long, AI responses may degrade. Use:
```
debate> status    # Check total characters
debate> new       # Reset both conversations
```

## Files

| File | Description |
|------|-------------|
| `run.sh` | One-command launcher (Chrome + app) |
| `debate.py` | Terminal interface |
| `web_app.py` | Web interface server |
| `templates/index.html` | Web UI template |
| `configs/default.json` | Default debate configuration |
