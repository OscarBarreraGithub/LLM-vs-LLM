---
description: Quick commands for the AI Debate Tool
allowed-tools: Bash(./run.sh:*), Bash(python3:*), Bash(curl:*), Bash(pgrep:*), Bash(pkill:*)
argument-hint: [start|stop|status|test]
---

# Debate Tool Commands

Quick commands to manage the AI Debate Tool.

## Usage

- `/debate start` - Launch the debate tool (Chrome + web server)
- `/debate stop` - Stop the running server
- `/debate status` - Check if server and Chrome are running
- `/debate test` - Verify Chrome connection and tab detection

## Commands

### start

```bash
./run.sh
```

Opens Chrome with debugging and starts the web UI at http://localhost:5050

### stop

```bash
pkill -f "python3 web_app.py" 2>/dev/null || echo "Server not running"
```

### status

```bash
echo "=== Flask Server ==="
pgrep -f "python3 web_app.py" && echo "Running" || echo "Not running"

echo ""
echo "=== Chrome Debug Port ==="
curl -s http://localhost:9222/json/version && echo "Connected" || echo "Not available"

echo ""
echo "=== Open Tabs ==="
curl -s http://localhost:9222/json 2>/dev/null | python3 -c "
import json, sys
try:
    tabs = json.load(sys.stdin)
    chatgpt = any('chatgpt.com' in t.get('url','') for t in tabs)
    gemini = any('gemini.google.com' in t.get('url','') for t in tabs)
    print(f'ChatGPT tab: {\"Found\" if chatgpt else \"Missing\"}'')
    print(f'Gemini tab: {\"Found\" if gemini else \"Missing\"}')
except:
    print('Could not parse tabs')
" 2>/dev/null || echo "Chrome not available"
```

### test

```bash
echo "Testing Chrome connection..."
curl -s http://localhost:9222/json | python3 -c "
import json, sys
tabs = json.load(sys.stdin)
print(f'Found {len(tabs)} tabs')
for t in tabs:
    print(f'  - {t.get(\"title\", \"?\")[:50]}')
"
```

## Default Action

If no argument provided, run `status`.
