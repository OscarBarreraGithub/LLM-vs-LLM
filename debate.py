#!/usr/bin/env python3
"""
AI Debate Tool - Streamlined version with customizable prompts and controls.

Usage:
    python3 debate.py                    # Interactive mode
    python3 debate.py --config my.yaml   # Use custom config
    python3 debate.py --rounds 5         # Run 5 rounds then pause

Setup:
    1. Launch Chrome: /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
         --remote-debugging-port=9222 --user-data-dir="/tmp/chrome-debug"
    2. Open tabs: chatgpt.com and gemini.google.com/app
    3. Log in to both
    4. Run this script
"""

import asyncio
import json
import sys
import argparse
from dataclasses import dataclass, field
from typing import Optional
import requests
import websockets


# ============================================================================
# CONFIGURATION - Edit these or load from file
# ============================================================================

@dataclass
class DebateConfig:
    """Configuration for the debate."""

    # Header prepended to messages sent to each AI
    header_chatgpt: str = "You are in a debate with Gemini."
    header_gemini: str = "You are in a debate with ChatGPT."

    # Role/position for each AI
    role_chatgpt: str = ""
    role_gemini: str = ""

    # Instructions appended to each message
    instructions: str = "Respond in 2-3 paragraphs. Be concise but thorough."

    # Convergence/goal instruction
    goal: str = ""

    # Delimiter between sections
    delimiter: str = "\n---\n"

    # Max characters per response before warning
    max_response_length: int = 3000

    # Max rounds before auto-pause (0 = unlimited)
    max_rounds: int = 0

    # Seconds between messages
    delay: int = 3


DEFAULT_CONFIG = DebateConfig()


# ============================================================================
# BROWSER CONTROL
# ============================================================================

class ChromeTab:
    """Low-level Chrome DevTools Protocol connection."""

    def __init__(self, ws_url: str):
        self.ws_url = ws_url
        self.ws = None
        self.msg_id = 0

    async def connect(self):
        self.ws = await websockets.connect(self.ws_url, max_size=None)

    async def send(self, method: str, params: dict = None):
        self.msg_id += 1
        msg = {"id": self.msg_id, "method": method, "params": params or {}}
        await self.ws.send(json.dumps(msg))
        while True:
            resp = json.loads(await self.ws.recv())
            if resp.get("id") == self.msg_id:
                return resp.get("result", {})

    async def evaluate(self, js: str):
        result = await self.send("Runtime.evaluate", {
            "expression": js,
            "returnByValue": True,
            "awaitPromise": True
        })
        return result.get("result", {}).get("value")

    async def type_text(self, text: str):
        await self.send("Input.insertText", {"text": text})

    async def close(self):
        if self.ws:
            await self.ws.close()


class ChatGPT:
    """ChatGPT browser controller."""

    def __init__(self, tab: ChromeTab):
        self.tab = tab
        self.name = "ChatGPT"

    async def send_message(self, text: str, max_retries: int = 3) -> bool:
        """Type and send a message with confirmation. Returns True if successful."""
        initial_count = await self.get_response_count()

        for attempt in range(max_retries):
            # Focus and clear input
            await self.tab.evaluate('''
                (() => {
                    const el = document.querySelector("#prompt-textarea") ||
                              document.querySelector("textarea");
                    if (el) { el.focus(); el.value = ""; }
                })()
            ''')
            await asyncio.sleep(0.3)

            # Type message
            await self.tab.type_text(text)
            await asyncio.sleep(0.5)

            # Click send
            clicked = await self.tab.evaluate('''
                (() => {
                    const btn = document.querySelector('[data-testid="send-button"]') ||
                               document.querySelector('button[aria-label*="Send"]');
                    if (btn && !btn.disabled) { btn.click(); return true; }
                    return false;
                })()
            ''')

            if not clicked:
                print(f"  [ChatGPT] Send button not clicked, attempt {attempt + 1}/{max_retries}")
                await asyncio.sleep(1)
                continue

            # Wait for confirmation: generation starts or response count increases
            confirmed = await self._wait_for_send_confirmation(initial_count, timeout=10)
            if confirmed:
                return True

            print(f"  [ChatGPT] Message not confirmed, attempt {attempt + 1}/{max_retries}")
            await asyncio.sleep(1)

        print("  [ChatGPT] WARNING: Failed to confirm message was sent after retries")
        return False

    async def _wait_for_send_confirmation(self, initial_count: int, timeout: int = 10) -> bool:
        """Wait for confirmation that message was sent."""
        elapsed = 0
        while elapsed < timeout:
            if await self.is_generating():
                return True
            if await self.get_response_count() > initial_count:
                return True
            await asyncio.sleep(0.5)
            elapsed += 0.5
        return False

    async def is_generating(self) -> bool:
        """Check if ChatGPT is still generating a response."""
        return await self.tab.evaluate('''
            (() => {
                const stop = document.querySelector('[data-testid="stop-button"]') ||
                            document.querySelector('button[aria-label*="Stop"]');
                return stop !== null;
            })()
        ''') or False

    async def get_last_response(self) -> str:
        """Get the most recent assistant response."""
        return await self.tab.evaluate('''
            (() => {
                const msgs = document.querySelectorAll('[data-message-author-role="assistant"]');
                if (msgs.length === 0) return "";
                const last = msgs[msgs.length - 1];
                const content = last.querySelector(".markdown") || last;
                return content.innerText.trim();
            })()
        ''') or ""

    async def get_response_count(self) -> int:
        """Get number of assistant responses (for tracking context)."""
        return await self.tab.evaluate('''
            document.querySelectorAll('[data-message-author-role="assistant"]').length
        ''') or 0

    async def start_new_chat(self):
        """Start a fresh conversation."""
        await self.tab.evaluate('''
            (() => {
                const newChat = document.querySelector('[data-testid="new-chat-button"]') ||
                               document.querySelector('a[href="/"]');
                if (newChat) newChat.click();
            })()
        ''')


class Gemini:
    """Gemini browser controller."""

    def __init__(self, tab: ChromeTab):
        self.tab = tab
        self.name = "Gemini"

    async def send_message(self, text: str, max_retries: int = 3) -> bool:
        """Type and send a message with confirmation. Returns True if successful."""
        initial_count = await self.get_response_count()

        for attempt in range(max_retries):
            # Focus and clear input
            await self.tab.evaluate('''
                (() => {
                    const el = document.querySelector(".ql-editor");
                    if (el) { el.click(); el.focus(); el.innerHTML = ""; }
                })()
            ''')
            await asyncio.sleep(0.3)

            # Type message
            await self.tab.type_text(text)
            await asyncio.sleep(0.5)

            # Click send
            clicked = await self.tab.evaluate('''
                (() => {
                    const buttons = Array.from(document.querySelectorAll("button"));
                    for (const btn of buttons) {
                        const label = (btn.getAttribute("aria-label") || "").toLowerCase();
                        if (label.includes("send")) { btn.click(); return true; }
                    }
                    return false;
                })()
            ''')

            if not clicked:
                print(f"  [Gemini] Send button not clicked, attempt {attempt + 1}/{max_retries}")
                await asyncio.sleep(1)
                continue

            # Wait for confirmation: generation starts or response count increases
            confirmed = await self._wait_for_send_confirmation(initial_count, timeout=10)
            if confirmed:
                return True

            print(f"  [Gemini] Message not confirmed, attempt {attempt + 1}/{max_retries}")
            await asyncio.sleep(1)

        print("  [Gemini] WARNING: Failed to confirm message was sent after retries")
        return False

    async def _wait_for_send_confirmation(self, initial_count: int, timeout: int = 10) -> bool:
        """Wait for confirmation that message was sent."""
        elapsed = 0
        while elapsed < timeout:
            if await self.is_generating():
                return True
            if await self.get_response_count() > initial_count:
                return True
            await asyncio.sleep(0.5)
            elapsed += 0.5
        return False

    async def is_generating(self) -> bool:
        """Check if Gemini is still generating."""
        # Check for streaming indicators or stop button
        return await self.tab.evaluate('''
            (() => {
                const stop = document.querySelector('button[aria-label*="Stop"]');
                const loading = document.querySelector('.loading-indicator');
                return stop !== null || loading !== null;
            })()
        ''') or False

    async def get_last_response(self) -> str:
        """Get the most recent model response."""
        return await self.tab.evaluate('''
            (() => {
                const msgs = document.querySelectorAll("message-content");
                for (let i = msgs.length - 1; i >= 0; i--) {
                    const text = msgs[i].innerText.trim();
                    if (text.length > 20) return text;
                }
                return "";
            })()
        ''') or ""

    async def get_response_count(self) -> int:
        """Get number of model responses."""
        return await self.tab.evaluate('''
            document.querySelectorAll("message-content").length
        ''') or 0

    async def start_new_chat(self):
        """Start a fresh conversation."""
        await self.tab.evaluate('''
            (() => {
                const newChat = document.querySelector('[aria-label*="New chat"]') ||
                               document.querySelector('a[href*="/app"]');
                if (newChat) newChat.click();
            })()
        ''')


# ============================================================================
# DEBATE CONTROLLER
# ============================================================================

class DebateController:
    """Main controller for AI debates."""

    def __init__(self, config: DebateConfig = None):
        self.config = config or DEFAULT_CONFIG
        self.chatgpt: Optional[ChatGPT] = None
        self.gemini: Optional[Gemini] = None
        self.round = 0
        self.total_rounds = 0
        self.paused = False
        self.history = []  # Track conversation for context monitoring

    async def connect(self):
        """Connect to Chrome tabs."""
        try:
            tabs = requests.get("http://localhost:9222/json", timeout=5).json()
        except:
            print("ERROR: Cannot connect to Chrome.")
            print("Make sure Chrome is running with:")
            print('  /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome \\')
            print('    --remote-debugging-port=9222 --user-data-dir="/tmp/chrome-debug"')
            return False

        chatgpt_info = next((t for t in tabs if "chatgpt.com" in t.get("url", "")), None)
        gemini_info = next((t for t in tabs if "gemini.google.com" in t.get("url", "")), None)

        if not chatgpt_info:
            print("ERROR: ChatGPT tab not found. Open https://chatgpt.com")
            return False
        if not gemini_info:
            print("ERROR: Gemini tab not found. Open https://gemini.google.com/app")
            return False

        chatgpt_tab = ChromeTab(chatgpt_info["webSocketDebuggerUrl"])
        gemini_tab = ChromeTab(gemini_info["webSocketDebuggerUrl"])

        await chatgpt_tab.connect()
        await gemini_tab.connect()

        self.chatgpt = ChatGPT(chatgpt_tab)
        self.gemini = Gemini(gemini_tab)

        print("Connected to both tabs.")
        return True

    def build_prompt(self, target: str, opponent_response: str = None,
                     custom_instruction: str = None) -> str:
        """Build a prompt with header, role, and content."""
        parts = []

        # Round info
        if self.total_rounds > 0:
            parts.append(f"[Round {self.round} of {self.total_rounds}]")

        # Header
        if target == "chatgpt":
            if self.config.header_chatgpt:
                parts.append(self.config.header_chatgpt)
            if self.config.role_chatgpt:
                parts.append(f"YOUR POSITION: {self.config.role_chatgpt}")
        else:
            if self.config.header_gemini:
                parts.append(self.config.header_gemini)
            if self.config.role_gemini:
                parts.append(f"YOUR POSITION: {self.config.role_gemini}")

        # Opponent's response
        if opponent_response:
            opponent_name = "Gemini" if target == "chatgpt" else "ChatGPT"
            parts.append(f"{opponent_name} says:{self.config.delimiter}{opponent_response}")

        # Custom instruction or default
        if custom_instruction:
            parts.append(custom_instruction)
        elif self.config.instructions:
            parts.append(self.config.instructions)

        # Goal
        if self.config.goal:
            parts.append(f"Goal: {self.config.goal}")

        return "\n\n".join(parts)

    async def wait_for_response(self, ai, timeout: int = 3600, initial_count: int = None) -> str:
        """Wait for AI to finish generating and return response."""
        # Get initial count if not provided
        if initial_count is None:
            initial_count = await ai.get_response_count()

        elapsed = 0
        generation_started = False

        # First, wait for generation to start (with shorter timeout)
        start_timeout = 15
        while elapsed < start_timeout:
            if await ai.is_generating():
                generation_started = True
                break
            # Also check if response count increased (fast response)
            if await ai.get_response_count() > initial_count:
                generation_started = True
                break
            await asyncio.sleep(0.5)
            elapsed += 0.5

        if not generation_started:
            print(f"  WARNING: {ai.name} generation did not start within {start_timeout}s")

        # Now wait for generation to complete
        while elapsed < timeout:
            # Check if still generating
            if not await ai.is_generating():
                # Double-check by waiting a moment
                await asyncio.sleep(1)
                if not await ai.is_generating():
                    break

            await asyncio.sleep(2)
            elapsed += 2

            # Progress indicator
            if int(elapsed) % 10 == 0 and elapsed > 10:
                print(f"  {ai.name} generating... ({int(elapsed)}s)")

        # Small buffer for final render
        await asyncio.sleep(0.5)
        response = await ai.get_last_response()

        # Warn if response is too long
        if len(response) > self.config.max_response_length:
            print(f"  WARNING: Response is {len(response)} chars (limit: {self.config.max_response_length})")

        return response

    async def send_and_wait(self, ai, prompt: str) -> str:
        """Send a message and wait for response."""
        print(f"\n>>> Sending to {ai.name}...")
        print(f"    Prompt preview: {prompt[:100]}...")

        success = await ai.send_message(prompt)
        if not success:
            print(f"  WARNING: Send button may not have been clicked")

        response = await self.wait_for_response(ai)

        if response:
            preview = response[:200] + "..." if len(response) > 200 else response
            print(f"\n<<< {ai.name} responded ({len(response)} chars):")
            print(f"    {preview}")
        else:
            print(f"  WARNING: Empty response from {ai.name}")

        return response

    async def run_round(self, chatgpt_prompt: str = None, gemini_prompt: str = None,
                        last_response: str = None, start_with: str = "chatgpt") -> str:
        """Run one round of debate. Returns the last response."""
        self.round += 1
        print(f"\n{'='*60}")
        print(f"ROUND {self.round}")
        print(f"{'='*60}")

        if start_with == "chatgpt":
            # ChatGPT turn
            prompt = chatgpt_prompt or self.build_prompt("chatgpt", last_response)
            response = await self.send_and_wait(self.chatgpt, prompt)
            self.history.append({"from": "chatgpt", "text": response})

            await asyncio.sleep(self.config.delay)

            # Gemini turn
            prompt = gemini_prompt or self.build_prompt("gemini", response)
            response = await self.send_and_wait(self.gemini, prompt)
            self.history.append({"from": "gemini", "text": response})
        else:
            # Gemini first
            prompt = gemini_prompt or self.build_prompt("gemini", last_response)
            response = await self.send_and_wait(self.gemini, prompt)
            self.history.append({"from": "gemini", "text": response})

            await asyncio.sleep(self.config.delay)

            # ChatGPT turn
            prompt = chatgpt_prompt or self.build_prompt("chatgpt", response)
            response = await self.send_and_wait(self.chatgpt, prompt)
            self.history.append({"from": "chatgpt", "text": response})

        return response

    async def close(self):
        """Close connections."""
        if self.chatgpt:
            await self.chatgpt.tab.close()
        if self.gemini:
            await self.gemini.tab.close()


# ============================================================================
# INTERACTIVE CLI
# ============================================================================

def print_help():
    print("""
COMMANDS:
  start <topic>     Start debate with initial topic
  round [n]         Run n rounds (default: 1)
  chatgpt <msg>     Send custom message to ChatGPT only
  gemini <msg>      Send custom message to Gemini only
  inject <msg>      Send same message to both AIs
  config            Show current configuration
  set <key> <val>   Update config (e.g., set role_chatgpt "argue for X")
  status            Show conversation stats
  new               Start fresh conversations in both tabs
  history           Show conversation history
  quit              Exit
  help              Show this help
""")


async def interactive_mode(controller: DebateController):
    """Run interactive CLI mode."""
    print("\n" + "="*60)
    print("AI DEBATE TOOL - Interactive Mode")
    print("="*60)
    print("Type 'help' for commands\n")

    if not await controller.connect():
        return

    last_response = None

    while True:
        try:
            cmd = input("\ndebate> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting...")
            break

        if not cmd:
            continue

        parts = cmd.split(maxsplit=1)
        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if command == "quit" or command == "exit":
            break

        elif command == "help":
            print_help()

        elif command == "start":
            if not args:
                print("Usage: start <topic>")
                continue
            # Set total_rounds to 1 for the initial round
            controller.total_rounds = controller.round + 1
            # Build initial prompts with topic
            chatgpt_prompt = controller.build_prompt("chatgpt", custom_instruction=f"Topic: {args}\n\nMake your opening argument.")
            gemini_prompt = None  # Will be built from ChatGPT's response
            last_response = await controller.run_round(chatgpt_prompt=chatgpt_prompt)

        elif command == "round":
            n = int(args) if args.isdigit() else 1
            # Set total_rounds to current + n
            controller.total_rounds = controller.round + n
            for _ in range(n):
                last_response = await controller.run_round(last_response=last_response)
                if controller.config.max_rounds and controller.round >= controller.config.max_rounds:
                    print(f"\nPaused: reached max_rounds ({controller.config.max_rounds})")
                    break

        elif command == "chatgpt":
            if not args:
                print("Usage: chatgpt <message>")
                continue
            last_response = await controller.send_and_wait(controller.chatgpt, args)
            controller.history.append({"from": "chatgpt", "text": last_response})

        elif command == "gemini":
            if not args:
                print("Usage: gemini <message>")
                continue
            last_response = await controller.send_and_wait(controller.gemini, args)
            controller.history.append({"from": "gemini", "text": last_response})

        elif command == "inject":
            if not args:
                print("Usage: inject <message>")
                continue
            print("Sending to both AIs...")
            await controller.send_and_wait(controller.chatgpt, args)
            await controller.send_and_wait(controller.gemini, args)

        elif command == "config":
            c = controller.config
            print(f"""
Current Configuration:
  header_chatgpt: {c.header_chatgpt[:50]}...
  header_gemini:  {c.header_gemini[:50]}...
  role_chatgpt:   {c.role_chatgpt or '(not set)'}
  role_gemini:    {c.role_gemini or '(not set)'}
  instructions:   {c.instructions[:50]}...
  goal:           {c.goal or '(not set)'}
  max_rounds:     {c.max_rounds}
  delay:          {c.delay}s
""")

        elif command == "set":
            try:
                key, val = args.split(maxsplit=1)
                val = val.strip('"\'')
                if hasattr(controller.config, key):
                    setattr(controller.config, key, val)
                    print(f"Set {key} = {val}")
                else:
                    print(f"Unknown config key: {key}")
            except ValueError:
                print("Usage: set <key> <value>")

        elif command == "status":
            print(f"""
Status:
  Rounds completed: {controller.round}
  Messages in history: {len(controller.history)}
  Total characters: {sum(len(m['text']) for m in controller.history)}
""")

        elif command == "new":
            print("Starting fresh conversations...")
            await controller.chatgpt.start_new_chat()
            await asyncio.sleep(1)
            await controller.gemini.start_new_chat()
            controller.round = 0
            controller.history = []
            last_response = None
            print("Done. Both conversations reset.")

        elif command == "history":
            if not controller.history:
                print("No history yet.")
            else:
                for i, m in enumerate(controller.history[-6:]):  # Last 6 messages
                    preview = m['text'][:150] + "..." if len(m['text']) > 150 else m['text']
                    print(f"\n[{m['from'].upper()}]: {preview}")

        else:
            print(f"Unknown command: {command}. Type 'help' for commands.")

    await controller.close()


# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="AI Debate Tool")
    parser.add_argument("--header-chatgpt", help="Header for ChatGPT prompts")
    parser.add_argument("--header-gemini", help="Header for Gemini prompts")
    parser.add_argument("--role-chatgpt", help="ChatGPT's position/role")
    parser.add_argument("--role-gemini", help="Gemini's position/role")
    parser.add_argument("--instructions", help="Instructions appended to prompts")
    parser.add_argument("--goal", help="Convergence/goal instruction")
    parser.add_argument("--max-rounds", type=int, help="Max rounds before pause")
    parser.add_argument("--delay", type=int, help="Seconds between messages")

    args = parser.parse_args()

    # Build config from args
    config = DebateConfig()
    if args.header_chatgpt:
        config.header_chatgpt = args.header_chatgpt
    if args.header_gemini:
        config.header_gemini = args.header_gemini
    if args.role_chatgpt:
        config.role_chatgpt = args.role_chatgpt
    if args.role_gemini:
        config.role_gemini = args.role_gemini
    if args.instructions:
        config.instructions = args.instructions
    if args.goal:
        config.goal = args.goal
    if args.max_rounds:
        config.max_rounds = args.max_rounds
    if args.delay:
        config.delay = args.delay

    controller = DebateController(config)
    asyncio.run(interactive_mode(controller))


if __name__ == "__main__":
    main()
