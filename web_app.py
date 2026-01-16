#!/usr/bin/env python3
"""
AI Debate Tool - Web Interface
"""

import json
import os
import threading
import time
from datetime import datetime
from flask import Flask, render_template, request, jsonify
import requests
from websocket import create_connection

app = Flask(__name__)

# Directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIGS_DIR = os.path.join(BASE_DIR, "configs")
CONVERSATIONS_DIR = os.path.join(BASE_DIR, "conversations")

# Ensure directories exist
os.makedirs(CONFIGS_DIR, exist_ok=True)
os.makedirs(CONVERSATIONS_DIR, exist_ok=True)

# Global state
debate_state = {
    "running": False,
    "paused": False,
    "round": 0,
    "total_rounds": 0,
    "history": [],
    "config": {
        # Initial prompts (Round 1 only)
        "initial_prompt_chatgpt": "",
        "initial_prompt_gemini": "",
        # Subsequent prompts (Round 2+)
        "subsequent_prompt_chatgpt": "",
        "subsequent_prompt_gemini": "",
        # Formatting instructions (appended to ALL prompts)
        "formatting_chatgpt": "",
        "formatting_gemini": "",
        # Whether to include ChatGPT's response in Gemini's first prompt
        "include_chatgpt_response_in_first": True,
        # Delay between messages
        "delay": 3
    }
}

state_lock = threading.Lock()


def add_to_history(entry):
    """Add an entry to history with automatic timestamp."""
    entry["timestamp"] = datetime.now().isoformat()
    debate_state["history"].append(entry)


class ChromeController:
    """Synchronous Chrome controller."""

    def __init__(self):
        self.chatgpt_ws = None
        self.gemini_ws = None
        self.msg_id = 0

    def connect(self):
        try:
            tabs = requests.get("http://localhost:9222/json", timeout=5).json()
        except Exception as e:
            return False, f"Cannot connect to Chrome: {e}"

        chatgpt_info = next((t for t in tabs if "chatgpt.com" in t.get("url", "")), None)
        gemini_info = next((t for t in tabs if "gemini.google.com" in t.get("url", "")), None)

        if not chatgpt_info:
            return False, "ChatGPT tab not found"
        if not gemini_info:
            return False, "Gemini tab not found"

        try:
            self.chatgpt_ws = create_connection(chatgpt_info["webSocketDebuggerUrl"])
            self.gemini_ws = create_connection(gemini_info["webSocketDebuggerUrl"])
        except Exception as e:
            return False, f"WebSocket connection failed: {e}"

        return True, "Connected"

    def close(self):
        if self.chatgpt_ws:
            self.chatgpt_ws.close()
        if self.gemini_ws:
            self.gemini_ws.close()

    def _send_cdp(self, ws, method, params=None):
        self.msg_id += 1
        msg = {"id": self.msg_id, "method": method, "params": params or {}}
        ws.send(json.dumps(msg))
        while True:
            resp = json.loads(ws.recv())
            if resp.get("id") == self.msg_id:
                return resp.get("result", {})

    def _evaluate(self, ws, js):
        result = self._send_cdp(ws, "Runtime.evaluate", {
            "expression": js,
            "returnByValue": True,
            "awaitPromise": True
        })
        return result.get("result", {}).get("value")

    def _type_text(self, ws, text):
        self._send_cdp(ws, "Input.insertText", {"text": text})

    def _activate_tab(self, ws):
        """Bring tab to front so interactions work reliably."""
        self._send_cdp(ws, "Page.bringToFront", {})

    def send_to_chatgpt(self, message, max_retries=3):
        """Send message to ChatGPT with confirmation that it was received."""
        self._activate_tab(self.chatgpt_ws)
        initial_count = self.get_chatgpt_response_count()

        for attempt in range(max_retries):
            # Focus and clear input
            self._evaluate(self.chatgpt_ws, '''
                (() => {
                    const el = document.querySelector("#prompt-textarea") || document.querySelector("textarea");
                    if (el) { el.focus(); el.value = ""; }
                })()
            ''')
            time.sleep(0.3)

            # Type message
            self._type_text(self.chatgpt_ws, message)
            time.sleep(0.5)

            # Click send button
            clicked = self._evaluate(self.chatgpt_ws, '''
                (() => {
                    const btn = document.querySelector('[data-testid="send-button"]') ||
                               document.querySelector('button[aria-label*="Send"]');
                    if (btn && !btn.disabled) { btn.click(); return true; }
                    return false;
                })()
            ''')

            if not clicked:
                print(f"  [ChatGPT] Send button not clicked, attempt {attempt + 1}/{max_retries}")
                time.sleep(1)
                continue

            # Wait for confirmation: either generating starts or response count increases
            confirmed = self._wait_for_send_confirmation(
                is_generating_fn=self.is_chatgpt_generating,
                get_count_fn=self.get_chatgpt_response_count,
                initial_count=initial_count,
                timeout=10
            )

            if confirmed:
                return True

            print(f"  [ChatGPT] Message not confirmed, attempt {attempt + 1}/{max_retries}")
            time.sleep(1)

        print("  [ChatGPT] WARNING: Failed to confirm message was sent after retries")
        return False

    def _wait_for_send_confirmation(self, is_generating_fn, get_count_fn, initial_count, timeout=10):
        """Wait for confirmation that a message was sent (generation started or new response appeared)."""
        start = time.time()
        while time.time() - start < timeout:
            # Check if generation has started
            if is_generating_fn():
                return True
            # Check if a new response has already appeared (fast response)
            if get_count_fn() > initial_count:
                return True
            time.sleep(0.5)
        return False

    def send_to_gemini(self, message, max_retries=3):
        """Send message to Gemini with confirmation that it was received."""
        self._activate_tab(self.gemini_ws)
        initial_count = self.get_gemini_response_count()

        for attempt in range(max_retries):
            # Focus input
            self._evaluate(self.gemini_ws, '''
                (() => {
                    const el = document.querySelector(".ql-editor");
                    if (el) { el.click(); el.focus(); el.innerHTML = ""; }
                })()
            ''')
            time.sleep(0.3)

            # Type message
            self._type_text(self.gemini_ws, message)
            time.sleep(0.5)

            # Click send button
            clicked = self._evaluate(self.gemini_ws, '''
                (() => {
                    const buttons = Array.from(document.querySelectorAll("button"));
                    for (const btn of buttons) {
                        if ((btn.getAttribute("aria-label") || "").toLowerCase().includes("send")) {
                            btn.click();
                            return true;
                        }
                    }
                    return false;
                })()
            ''')

            if not clicked:
                print(f"  [Gemini] Send button not clicked, attempt {attempt + 1}/{max_retries}")
                time.sleep(1)
                continue

            # Wait for confirmation: either generating starts or response count increases
            confirmed = self._wait_for_send_confirmation(
                is_generating_fn=self.is_gemini_generating,
                get_count_fn=self.get_gemini_response_count,
                initial_count=initial_count,
                timeout=10
            )

            if confirmed:
                return True

            print(f"  [Gemini] Message not confirmed, attempt {attempt + 1}/{max_retries}")
            time.sleep(1)

        print("  [Gemini] WARNING: Failed to confirm message was sent after retries")
        return False

    def is_chatgpt_generating(self):
        return self._evaluate(self.chatgpt_ws, '''
            document.querySelector('[data-testid="stop-button"]') !== null
        ''') or False

    def is_gemini_generating(self):
        return self._evaluate(self.gemini_ws, '''
            document.querySelector('button[aria-label*="Stop"]') !== null
        ''') or False

    def get_chatgpt_response_count(self):
        """Get current number of assistant responses."""
        return self._evaluate(self.chatgpt_ws, '''
            document.querySelectorAll('[data-message-author-role="assistant"]').length
        ''') or 0

    def get_gemini_response_count(self):
        """Get current number of model responses."""
        return self._evaluate(self.gemini_ws, '''
            document.querySelectorAll("message-content").length
        ''') or 0

    def get_chatgpt_response(self):
        self._activate_tab(self.chatgpt_ws)
        return self._evaluate(self.chatgpt_ws, '''
            (() => {
                // Try multiple selectors - ChatGPT UI changes frequently
                let msgs = document.querySelectorAll('[data-message-author-role="assistant"]');
                if (msgs.length === 0) {
                    msgs = document.querySelectorAll('.agent-turn');
                }
                if (msgs.length === 0) {
                    msgs = document.querySelectorAll('[class*="assistant"]');
                }
                if (msgs.length === 0) return "";
                const last = msgs[msgs.length - 1];
                const content = last.querySelector(".markdown") ||
                               last.querySelector('[class*="markdown"]') ||
                               last;
                return content.innerText.trim();
            })()
        ''') or ""

    def get_gemini_response(self):
        self._activate_tab(self.gemini_ws)
        return self._evaluate(self.gemini_ws, '''
            (() => {
                const msgs = document.querySelectorAll("message-content");
                for (let i = msgs.length - 1; i >= 0; i--) {
                    const text = msgs[i].innerText.trim();
                    if (text.length > 20) return text;
                }
                return "";
            })()
        ''') or ""

    def new_chat_chatgpt(self):
        self._activate_tab(self.chatgpt_ws)
        self._evaluate(self.chatgpt_ws, '''
            (document.querySelector('[data-testid="new-chat-button"]') ||
             document.querySelector('a[href="/"]'))?.click()
        ''')

    def new_chat_gemini(self):
        self._activate_tab(self.gemini_ws)
        self._evaluate(self.gemini_ws, '''
            document.querySelector('[aria-label*="New chat"]')?.click()
        ''')


def build_prompt(target, opponent_response=None, topic=None, current_round=None, total_rounds=None):
    """Build prompt using the new template system.

    Templates can use these placeholders:
    - {{topic}} - the debate topic
    - {{opponent_response}} - the other AI's response
    - {{round}} - current round number
    - {{total_rounds}} - total number of rounds
    """
    config = debate_state["config"]

    # For round 1: ChatGPT uses initial, Gemini uses initial
    # For round 2+: Both use subsequent
    if current_round == 1:
        if target == "chatgpt":
            template = config.get("initial_prompt_chatgpt", "")
        else:
            template = config.get("initial_prompt_gemini", "")
    else:
        if target == "chatgpt":
            template = config.get("subsequent_prompt_chatgpt", "")
        else:
            template = config.get("subsequent_prompt_gemini", "")

    # Determine what opponent_response to use
    effective_opponent_response = opponent_response or ""

    # For Gemini's first prompt, check if we should include ChatGPT's response
    if current_round == 1 and target == "gemini":
        include_response = config.get("include_chatgpt_response_in_first", True)
        if not include_response:
            effective_opponent_response = ""

    # Replace placeholders
    prompt = template
    prompt = prompt.replace("{{topic}}", topic or "")
    prompt = prompt.replace("{{opponent_response}}", effective_opponent_response)
    prompt = prompt.replace("{{round}}", str(current_round or ""))
    prompt = prompt.replace("{{total_rounds}}", str(total_rounds or ""))

    # Add round info at the top if we have it
    if current_round and total_rounds:
        prompt = f"[Round {current_round} of {total_rounds}]\n\n{prompt}"

    # Append formatting instructions
    formatting_key = f"formatting_{target}"
    formatting = config.get(formatting_key, "")
    if formatting:
        prompt = f"{prompt}\n\n{formatting}"

    return prompt


def wait_for_response(chrome, target, timeout=3600, initial_count=None):
    """Wait for AI to finish generating and return response.

    Args:
        chrome: ChromeController instance
        target: "chatgpt" or "gemini"
        timeout: Max seconds to wait
        initial_count: Response count before sending (for verification)
    """
    is_gen = chrome.is_chatgpt_generating if target == "chatgpt" else chrome.is_gemini_generating
    get_resp = chrome.get_chatgpt_response if target == "chatgpt" else chrome.get_gemini_response
    get_count = chrome.get_chatgpt_response_count if target == "chatgpt" else chrome.get_gemini_response_count

    # Get initial count if not provided
    if initial_count is None:
        initial_count = get_count()

    elapsed = 0
    generation_started = False

    # First, wait for generation to start (with shorter timeout)
    start_timeout = 15
    while elapsed < start_timeout:
        if debate_state["paused"]:
            break
        if is_gen():
            generation_started = True
            break
        # Also check if response count increased (fast response)
        if get_count() > initial_count:
            generation_started = True
            break
        time.sleep(0.5)
        elapsed += 0.5

    if not generation_started:
        print(f"  [{target}] WARNING: Generation did not start within {start_timeout}s")

    # Now wait for generation to complete
    while elapsed < timeout:
        if debate_state["paused"]:
            break
        if not is_gen():
            # Double-check by waiting a moment and checking again
            time.sleep(1)
            if not is_gen():
                break
        time.sleep(2)
        elapsed += 2

        # Progress indicator
        if int(elapsed) % 10 == 0 and elapsed > 10:
            print(f"  [{target}] Still generating... ({int(elapsed)}s)")

    # Small buffer for final render
    time.sleep(0.5)
    return get_resp()


def run_debate_round(chrome, topic=None, last_response=None):
    with state_lock:
        debate_state["round"] += 1
        current_round = debate_state["round"]
        total_rounds = debate_state["total_rounds"]

    # ChatGPT turn
    prompt = build_prompt("chatgpt", opponent_response=last_response, topic=topic, current_round=current_round, total_rounds=total_rounds)

    # Get count before sending for verification
    chatgpt_initial_count = chrome.get_chatgpt_response_count()
    sent = chrome.send_to_chatgpt(prompt)

    with state_lock:
        add_to_history({
            "round": current_round,
            "from": "chatgpt",
            "type": "prompt",
            "text": prompt
        })

    if not sent:
        print(f"  [Round {current_round}] ChatGPT send failed, attempting to continue...")

    chatgpt_response = wait_for_response(chrome, "chatgpt", initial_count=chatgpt_initial_count)

    with state_lock:
        add_to_history({
            "round": current_round,
            "from": "chatgpt",
            "type": "response",
            "text": chatgpt_response
        })

    if debate_state["paused"]:
        return chatgpt_response

    time.sleep(debate_state["config"]["delay"])

    # Gemini turn
    prompt = build_prompt("gemini", opponent_response=chatgpt_response, topic=topic, current_round=current_round, total_rounds=total_rounds)

    # Get count before sending for verification
    gemini_initial_count = chrome.get_gemini_response_count()
    sent = chrome.send_to_gemini(prompt)

    with state_lock:
        add_to_history({
            "round": current_round,
            "from": "gemini",
            "type": "prompt",
            "text": prompt
        })

    if not sent:
        print(f"  [Round {current_round}] Gemini send failed, attempting to continue...")

    gemini_response = wait_for_response(chrome, "gemini", initial_count=gemini_initial_count)

    with state_lock:
        add_to_history({
            "round": current_round,
            "from": "gemini",
            "type": "response",
            "text": gemini_response
        })

    return gemini_response


def debate_loop(topic, num_rounds):
    with state_lock:
        debate_state["total_rounds"] = num_rounds

    chrome = ChromeController()
    success, msg = chrome.connect()

    if not success:
        with state_lock:
            debate_state["running"] = False
            add_to_history({"from": "system", "type": "error", "text": msg})
        return

    try:
        # Store topic for use in prompts
        debate_state["topic"] = topic

        # Run first round
        last_response = run_debate_round(chrome, topic=topic, last_response=None)

        for _ in range(num_rounds - 1):
            if debate_state["paused"] or not debate_state["running"]:
                break
            time.sleep(debate_state["config"]["delay"])
            last_response = run_debate_round(chrome, topic=topic, last_response=last_response)
    except Exception as e:
        with state_lock:
            add_to_history({"from": "system", "type": "error", "text": str(e)})
    finally:
        chrome.close()
        with state_lock:
            debate_state["running"] = False


def export_to_latex(history, topic="AI Debate"):
    """Export conversation history to LaTeX format."""
    lines = [
        r"\documentclass{article}",
        r"\usepackage{amsmath,amssymb}",
        r"\usepackage[margin=1in]{geometry}",
        r"\usepackage{xcolor}",
        r"\definecolor{chatgpt}{RGB}{16,163,127}",
        r"\definecolor{gemini}{RGB}{139,92,246}",
        r"",
        r"\title{" + topic.replace("_", r"\_") + r"}",
        r"\date{\today}",
        r"",
        r"\begin{document}",
        r"\maketitle",
        r""
    ]

    for item in history:
        if item.get("type") != "response":
            continue

        speaker = item.get("from", "unknown")
        text = item.get("text", "")
        round_num = item.get("round", "")

        # Escape LaTeX special characters (but preserve math)
        # Simple escape - user may need to clean up
        text = text.replace("&", r"\&")
        text = text.replace("%", r"\%")
        text = text.replace("#", r"\#")

        color = "chatgpt" if speaker == "chatgpt" else "gemini"
        name = "ChatGPT" if speaker == "chatgpt" else "Gemini"

        lines.append(r"\subsection*{\textcolor{" + color + r"}{" + name + r"}" + (f" (Round {round_num})" if round_num else "") + r"}")
        lines.append(r"")
        lines.append(text)
        lines.append(r"")
        lines.append(r"\vspace{1em}")
        lines.append(r"")

    lines.append(r"\end{document}")

    return "\n".join(lines)


# Flask routes
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/state")
def get_state():
    with state_lock:
        return jsonify(debate_state)


@app.route("/api/start", methods=["POST"])
def start_debate():
    data = request.json
    topic = data.get("topic", "")
    num_rounds = data.get("rounds", 3)

    if not topic:
        return jsonify({"error": "Topic required"}), 400

    with state_lock:
        if debate_state["running"]:
            return jsonify({"error": "Debate already running"}), 400
        debate_state["running"] = True
        debate_state["paused"] = False

    thread = threading.Thread(target=debate_loop, args=(topic, num_rounds))
    thread.daemon = True
    thread.start()

    return jsonify({"success": True})


@app.route("/api/pause", methods=["POST"])
def pause_debate():
    with state_lock:
        debate_state["paused"] = True
    return jsonify({"success": True})


@app.route("/api/resume", methods=["POST"])
def resume_debate():
    data = request.json
    num_rounds = data.get("rounds", 1)

    with state_lock:
        if debate_state["running"]:
            debate_state["paused"] = False
            return jsonify({"success": True, "message": "Resumed"})

        debate_state["running"] = True
        debate_state["paused"] = False
        # Set total rounds to current + new rounds being added
        debate_state["total_rounds"] = debate_state["round"] + num_rounds

        last_resp = None
        for item in reversed(debate_state["history"]):
            if item.get("type") == "response":
                last_resp = item.get("text")
                break

    def continue_debate():
        chrome = ChromeController()
        success, _ = chrome.connect()
        if not success:
            with state_lock:
                debate_state["running"] = False
            return

        try:
            response = last_resp
            topic = debate_state.get("topic", "")
            for _ in range(num_rounds):
                if debate_state["paused"]:
                    break
                response = run_debate_round(chrome, topic=topic, last_response=response)
                time.sleep(debate_state["config"]["delay"])
        finally:
            chrome.close()
            with state_lock:
                debate_state["running"] = False

    thread = threading.Thread(target=continue_debate)
    thread.daemon = True
    thread.start()

    return jsonify({"success": True})


@app.route("/api/stop", methods=["POST"])
def stop_debate():
    with state_lock:
        debate_state["running"] = False
        debate_state["paused"] = True
    return jsonify({"success": True})


@app.route("/api/send", methods=["POST"])
def send_message():
    data = request.json
    target = data.get("target")
    message = data.get("message")

    if target not in ["chatgpt", "gemini"]:
        return jsonify({"error": "Invalid target"}), 400
    if not message:
        return jsonify({"error": "Message required"}), 400

    chrome = ChromeController()
    success, msg = chrome.connect()

    if not success:
        return jsonify({"error": msg})

    try:
        if target == "chatgpt":
            initial_count = chrome.get_chatgpt_response_count()
            sent = chrome.send_to_chatgpt(message)
            if not sent:
                return jsonify({"error": "Failed to send message to ChatGPT"}), 500
            response = wait_for_response(chrome, "chatgpt", initial_count=initial_count)
        else:
            initial_count = chrome.get_gemini_response_count()
            sent = chrome.send_to_gemini(message)
            if not sent:
                return jsonify({"error": "Failed to send message to Gemini"}), 500
            response = wait_for_response(chrome, "gemini", initial_count=initial_count)

        with state_lock:
            add_to_history({
                "from": target,
                "type": "response",
                "text": response
            })

        return jsonify({"response": response})
    finally:
        chrome.close()


@app.route("/api/config", methods=["POST"])
def update_config():
    data = request.json
    with state_lock:
        for key, value in data.items():
            if key in debate_state["config"]:
                debate_state["config"][key] = value
    return jsonify({"success": True})


@app.route("/api/config/save", methods=["POST"])
def save_config():
    """Save current config to a file."""
    data = request.json
    name = data.get("name", "default")
    # Sanitize filename
    name = "".join(c for c in name if c.isalnum() or c in "-_")
    if not name:
        name = "default"

    filepath = os.path.join(CONFIGS_DIR, f"{name}.json")

    with state_lock:
        config_to_save = debate_state["config"].copy()

    with open(filepath, "w") as f:
        json.dump(config_to_save, f, indent=2)

    return jsonify({"success": True, "path": filepath})


@app.route("/api/config/load", methods=["POST"])
def load_config():
    """Load config from a file."""
    data = request.json
    name = data.get("name", "default")
    name = "".join(c for c in name if c.isalnum() or c in "-_")

    filepath = os.path.join(CONFIGS_DIR, f"{name}.json")

    if not os.path.exists(filepath):
        return jsonify({"error": f"Config '{name}' not found"}), 404

    with open(filepath, "r") as f:
        loaded_config = json.load(f)

    with state_lock:
        for key, value in loaded_config.items():
            if key in debate_state["config"]:
                debate_state["config"][key] = value

    return jsonify({"success": True, "config": loaded_config})


@app.route("/api/config/list")
def list_configs():
    """List saved configs."""
    configs = []
    for f in os.listdir(CONFIGS_DIR):
        if f.endswith(".json"):
            configs.append(f[:-5])  # Remove .json extension
    return jsonify({"configs": sorted(configs)})


@app.route("/api/export/latex", methods=["POST"])
def export_latex():
    """Export conversation to LaTeX file."""
    data = request.json
    topic = data.get("topic", "AI_Debate")
    # Sanitize filename
    filename = "".join(c for c in topic if c.isalnum() or c in "-_ ")
    filename = filename.replace(" ", "_")
    if not filename:
        filename = "debate"

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{filename}_{timestamp}.tex"
    filepath = os.path.join(CONVERSATIONS_DIR, filename)

    with state_lock:
        latex_content = export_to_latex(debate_state["history"], topic)

    with open(filepath, "w") as f:
        f.write(latex_content)

    return jsonify({"success": True, "path": filepath, "filename": filename})


@app.route("/api/new", methods=["POST"])
def new_chat():
    chrome = ChromeController()
    success, msg = chrome.connect()

    if not success:
        return jsonify({"error": msg})

    try:
        chrome.new_chat_chatgpt()
        time.sleep(1)
        chrome.new_chat_gemini()

        with state_lock:
            debate_state["round"] = 0
            debate_state["history"] = []

        return jsonify({"success": True})
    finally:
        chrome.close()


@app.route("/api/clear-history", methods=["POST"])
def clear_history():
    with state_lock:
        debate_state["history"] = []
        debate_state["round"] = 0
    return jsonify({"success": True})


@app.route("/api/summary", methods=["POST"])
def request_summary():
    """Request a summary from ChatGPT, Gemini, or both."""
    data = request.json
    target = data.get("target", "both")  # chatgpt, gemini, or both

    if target not in ("chatgpt", "gemini", "both"):
        return jsonify({"error": "Invalid target"}), 400

    chrome = ChromeController()
    success, msg = chrome.connect()

    if not success:
        return jsonify({"error": msg})

    summary_prompt = """Please provide a brief summary of our discussion so far. Include:

1. **Key Findings**: What main points or conclusions emerged?
2. **Areas of Agreement**: Where did we find common ground?
3. **Areas of Disagreement**: What points remain contested or unresolved?

Keep your summary concise (3-4 paragraphs max)."""

    results = {}

    try:
        if target in ("chatgpt", "both"):
            initial_count = chrome.get_chatgpt_response_count()
            sent = chrome.send_to_chatgpt(summary_prompt)
            with state_lock:
                add_to_history({
                    "round": debate_state["round"],
                    "from": "chatgpt",
                    "type": "summary_request",
                    "text": summary_prompt
                })
            if sent:
                response = wait_for_response(chrome, "chatgpt", timeout=90, initial_count=initial_count)
            else:
                response = "[Failed to send summary request]"
            with state_lock:
                add_to_history({
                    "round": debate_state["round"],
                    "from": "chatgpt",
                    "type": "summary",
                    "text": response
                })
            results["chatgpt"] = response

            if target == "both":
                time.sleep(2)

        if target in ("gemini", "both"):
            initial_count = chrome.get_gemini_response_count()
            sent = chrome.send_to_gemini(summary_prompt)
            with state_lock:
                add_to_history({
                    "round": debate_state["round"],
                    "from": "gemini",
                    "type": "summary_request",
                    "text": summary_prompt
                })
            if sent:
                response = wait_for_response(chrome, "gemini", timeout=90, initial_count=initial_count)
            else:
                response = "[Failed to send summary request]"
            with state_lock:
                add_to_history({
                    "round": debate_state["round"],
                    "from": "gemini",
                    "type": "summary",
                    "text": response
                })
            results["gemini"] = response

        return jsonify({"success": True, "summaries": results})
    finally:
        chrome.close()


if __name__ == "__main__":
    print("\n" + "="*50)
    print("AI Debate Tool - Web Interface")
    print("="*50)
    print(f"\nConfigs directory: {CONFIGS_DIR}")
    print(f"Conversations directory: {CONVERSATIONS_DIR}")
    print("\nOpen http://localhost:5050 in your browser\n")
    app.run(host="0.0.0.0", port=5050, debug=False, threaded=True)
