---
paths:
  - "debate.py"
  - "web_app.py"
---

# Browser Automation Guidelines

## Chrome DevTools Protocol

### Connection

```python
# Get available tabs
tabs = requests.get("http://localhost:9222/json").json()

# Connect to specific tab
ws = websockets.connect(tab["webSocketDebuggerUrl"])
```

### Common CDP Commands

```python
# Execute JavaScript
await tab.send("Runtime.evaluate", {
    "expression": js_code,
    "returnByValue": True,
    "awaitPromise": True
})

# Type text (requires element focus)
await tab.send("Input.insertText", {"text": text})
```

## Selector Maintenance

**ChatGPT and Gemini frequently update their UIs.** Selectors break regularly.

### When Selectors Break

1. Open browser DevTools (F12)
2. Inspect the target element
3. Find a stable selector (prefer `data-testid`, `aria-label`)
4. Update the selector in code
5. Test both send and receive operations

### Current Selectors (may be outdated)

**ChatGPT:**
- Input: `#prompt-textarea`
- Send: `[data-testid="send-button"]`
- Response: `[data-message-author-role="assistant"]`
- Generating: `[data-testid="stop-button"]`

**Gemini:**
- Input: `.ql-editor`
- Send: `[aria-label*="Send message"]`
- Response: `.message-content`, `model-response`

### Certainty Note

**Selector changes are high-risk.** Always:
- Test both ChatGPT AND Gemini
- Verify send, receive, and generation detection
- Report certainty < 7 for any selector modifications

## Timing and Waits

### Response Detection

```python
# Wait for generation to start (stop button appears)
# Then wait for generation to end (stop button disappears)
# Finally verify response count increased
```

### Recommended Waits

- After focus: 100ms
- After typing: 200ms
- After send click: 500ms
- Between messages: 3+ seconds
- Response timeout: 120 seconds

## Thread Safety

In `web_app.py`, always use the lock:

```python
with state_lock:
    debate_state["running"] = True
```
