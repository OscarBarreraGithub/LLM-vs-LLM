---
paths:
  - "**/*.py"
---

# Python Code Guidelines

## Style

- Follow PEP 8 conventions
- Use 4-space indentation
- Max line length: 100 characters (flexible for readability)
- Use double quotes for strings

## Structure

- Group imports: stdlib, third-party, local
- Use dataclasses for configuration objects
- Prefer explicit over implicit

## Patterns in This Project

### Async Code (debate.py)

```python
async def do_something():
    result = await some_async_call()
    return result
```

### Synchronous Code (web_app.py)

```python
def do_something():
    # Thread-safe state access
    with state_lock:
        state["key"] = value
```

### Error Handling

```python
try:
    result = risky_operation()
except SpecificException as e:
    # Log and handle gracefully
    print(f"Error: {e}")
    return None
```

## Type Hints

- Use type hints for function signatures
- Optional for internal/private functions
- Always for public API functions

```python
def process_response(text: str, timeout: int = 30) -> Optional[str]:
    ...
```

## Testing

- No test framework currently - manual testing via `./run.sh`
- Test browser automation with both ChatGPT and Gemini tabs open
