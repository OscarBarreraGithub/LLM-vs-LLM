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
        # System prompt prepended to ALL messages (fully customizable)
        "system_prompt": "",
        # Separate system prompt for Gemini (if empty, uses main system_prompt)
        "system_prompt_gemini": "",
        # One-time context sent to both AIs at the start
        "initial_context": "",
        # Whether to include "You are debating X" header
        "include_opponent_header": True,
        # Role/position for each AI
        "role_chatgpt": "",
        "role_gemini": "",
        # Instructions appended to prompts
        "instructions": "Respond in 2-3 concise paragraphs. Use LaTeX notation for any mathematical expressions (e.g., $x^2$ for inline, $$\\int f(x)dx$$ for display).",
        # Goal/convergence instruction
        "goal": "",
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

    def send_to_chatgpt(self, message):
        self._activate_tab(self.chatgpt_ws)
        self._evaluate(self.chatgpt_ws, '''
            (() => {
                const el = document.querySelector("#prompt-textarea") || document.querySelector("textarea");
                if (el) { el.focus(); el.value = ""; }
            })()
        ''')
        time.sleep(0.2)
        self._type_text(self.chatgpt_ws, message)
        time.sleep(0.3)
        self._evaluate(self.chatgpt_ws, '''
            (() => {
                const btn = document.querySelector('[data-testid="send-button"]') ||
                           document.querySelector('button[aria-label*="Send"]');
                if (btn && !btn.disabled) btn.click();
            })()
        ''')

    def send_to_gemini(self, message):
        self._activate_tab(self.gemini_ws)
        self._evaluate(self.gemini_ws, '''
            (() => {
                const el = document.querySelector(".ql-editor");
                if (el) { el.click(); el.focus(); }
            })()
        ''')
        time.sleep(0.2)
        self._type_text(self.gemini_ws, message)
        time.sleep(0.3)
        self._evaluate(self.gemini_ws, '''
            (() => {
                const buttons = Array.from(document.querySelectorAll("button"));
                for (const btn of buttons) {
                    if ((btn.getAttribute("aria-label") || "").toLowerCase().includes("send")) {
                        btn.click(); break;
                    }
                }
            })()
        ''')

    def is_chatgpt_generating(self):
        return self._evaluate(self.chatgpt_ws, '''
            document.querySelector('[data-testid="stop-button"]') !== null
        ''') or False

    def is_gemini_generating(self):
        return self._evaluate(self.gemini_ws, '''
            document.querySelector('button[aria-label*="Stop"]') !== null
        ''') or False

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


def build_prompt(target, opponent_response=None, custom=None, current_round=None, total_rounds=None):
    """Build prompt with config."""
    config = debate_state["config"]
    parts = []

    # Round info
    if current_round and total_rounds:
        parts.append(f"[Round {current_round} of {total_rounds}]")

    # System prompt (use Gemini-specific if available for Gemini)
    if target == "gemini" and config["system_prompt_gemini"]:
        parts.append(config["system_prompt_gemini"])
    elif config["system_prompt"]:
        parts.append(config["system_prompt"])

    # Opponent header (optional)
    if config["include_opponent_header"]:
        opponent = "Gemini" if target == "chatgpt" else "ChatGPT"
        parts.append(f"You are in a debate with {opponent}.")

    # Role/position
    role = config["role_chatgpt"] if target == "chatgpt" else config["role_gemini"]
    if role:
        parts.append(f"YOUR POSITION: {role}")

    # Opponent's response
    if opponent_response:
        opponent_name = "Gemini" if target == "chatgpt" else "ChatGPT"
        parts.append(f"{opponent_name} says:\n---\n{opponent_response}\n---")

    # Custom instruction or default
    if custom:
        parts.append(custom)
    elif config["instructions"]:
        parts.append(config["instructions"])

    # Goal
    if config["goal"]:
        parts.append(f"Goal: {config['goal']}")

    return "\n\n".join(parts)


def wait_for_response(chrome, target, timeout=120):
    time.sleep(2)
    is_gen = chrome.is_chatgpt_generating if target == "chatgpt" else chrome.is_gemini_generating
    get_resp = chrome.get_chatgpt_response if target == "chatgpt" else chrome.get_gemini_response

    for _ in range(timeout // 2):
        if debate_state["paused"]:
            break
        if not is_gen():
            time.sleep(1)
            break
        time.sleep(2)

    return get_resp()


def run_debate_round(chrome, initial_prompt=None, last_response=None):
    with state_lock:
        debate_state["round"] += 1
        current_round = debate_state["round"]
        total_rounds = debate_state["total_rounds"]

    # ChatGPT turn
    prompt = initial_prompt or build_prompt("chatgpt", last_response, current_round=current_round, total_rounds=total_rounds)
    chrome.send_to_chatgpt(prompt)

    with state_lock:
        add_to_history({
            "round": current_round,
            "from": "chatgpt",
            "type": "prompt",
            "text": prompt
        })

    chatgpt_response = wait_for_response(chrome, "chatgpt")

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
    prompt = build_prompt("gemini", chatgpt_response, current_round=current_round, total_rounds=total_rounds)
    chrome.send_to_gemini(prompt)

    with state_lock:
        add_to_history({
            "round": current_round,
            "from": "gemini",
            "type": "prompt",
            "text": prompt
        })

    gemini_response = wait_for_response(chrome, "gemini")

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
        # Send initial context to both AIs if provided
        initial_context = debate_state["config"].get("initial_context", "").strip()
        if initial_context:
            context_msg = f"Context for this discussion:\n\n{initial_context}\n\nPlease acknowledge you understand this context briefly."

            # Send to ChatGPT
            chrome.send_to_chatgpt(context_msg)
            with state_lock:
                add_to_history({
                    "round": 0,
                    "from": "chatgpt",
                    "type": "context",
                    "text": context_msg
                })
            wait_for_response(chrome, "chatgpt", timeout=60)

            time.sleep(1)

            # Send to Gemini
            chrome.send_to_gemini(context_msg)
            with state_lock:
                add_to_history({
                    "round": 0,
                    "from": "gemini",
                    "type": "context",
                    "text": context_msg
                })
            wait_for_response(chrome, "gemini", timeout=60)

            time.sleep(debate_state["config"]["delay"])

        initial = build_prompt("chatgpt", custom=f"Topic: {topic}\n\nMake your opening argument.", current_round=1, total_rounds=num_rounds)
        last_response = run_debate_round(chrome, initial_prompt=initial)

        for _ in range(num_rounds - 1):
            if debate_state["paused"] or not debate_state["running"]:
                break
            time.sleep(debate_state["config"]["delay"])
            last_response = run_debate_round(chrome, last_response=last_response)
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
            for _ in range(num_rounds):
                if debate_state["paused"]:
                    break
                response = run_debate_round(chrome, last_response=response)
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
            chrome.send_to_chatgpt(message)
            response = wait_for_response(chrome, "chatgpt")
        else:
            chrome.send_to_gemini(message)
            response = wait_for_response(chrome, "gemini")

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
            chrome.send_to_chatgpt(summary_prompt)
            with state_lock:
                add_to_history({
                    "round": debate_state["round"],
                    "from": "chatgpt",
                    "type": "summary_request",
                    "text": summary_prompt
                })
            response = wait_for_response(chrome, "chatgpt", timeout=90)
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
            chrome.send_to_gemini(summary_prompt)
            with state_lock:
                add_to_history({
                    "round": debate_state["round"],
                    "from": "gemini",
                    "type": "summary_request",
                    "text": summary_prompt
                })
            response = wait_for_response(chrome, "gemini", timeout=90)
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
