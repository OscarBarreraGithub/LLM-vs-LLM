---
paths:
  - "web_app.py"
  - "templates/**"
---

# Flask Guidelines

## Application Structure

```python
app = Flask(__name__)

# Global state with thread lock
debate_state = {...}
state_lock = threading.Lock()
```

## Route Patterns

### JSON API Routes

```python
@app.route("/api/action", methods=["POST"])
def api_action():
    data = request.get_json() or {}

    # Validate input
    required_field = data.get("field")
    if not required_field:
        return jsonify({"error": "field required"}), 400

    # Thread-safe state modification
    with state_lock:
        debate_state["key"] = value

    return jsonify({"success": True, "data": result})
```

### Page Routes

```python
@app.route("/")
def index():
    return render_template("index.html")
```

## State Management

All state is in `debate_state` dict. Always use `state_lock`:

```python
# Reading (quick read can skip lock, but prefer using it)
with state_lock:
    current = debate_state["round"]

# Writing (always use lock)
with state_lock:
    debate_state["round"] += 1
    debate_state["history"].append(entry)
```

## Background Threads

Debate runs in background thread:

```python
def debate_loop():
    """Runs in separate thread."""
    global debate_state

    # Long-running operation
    while debate_state["running"]:
        # Do work
        with state_lock:
            debate_state["round"] += 1

# Start thread
thread = threading.Thread(target=debate_loop)
thread.daemon = True
thread.start()
```

## Templates

- Single template: `templates/index.html`
- Inline JavaScript/CSS (no separate static files)
- Uses Jinja2 templating

## Running

```bash
# Development
python3 web_app.py  # Runs on localhost:5050

# Or via run.sh (also starts Chrome)
./run.sh
```
