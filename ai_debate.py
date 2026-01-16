#!/usr/bin/env python3
"""
AI Debate Tool - Make ChatGPT and Gemini argue with each other.

Setup:
1. Close Chrome completely
2. Launch Chrome with debugging enabled:
   /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222
3. Open two tabs: https://chatgpt.com and https://gemini.google.com/app
4. Make sure you're logged in to both
5. Run this script: python3 ai_debate.py

Dependencies:
    pip install websockets requests
"""

import asyncio
import json
import requests
import websockets
import argparse
import sys
import time


def get_chrome_tabs():
    """Get list of open Chrome tabs from the debug endpoint."""
    try:
        response = requests.get("http://localhost:9222/json")
        return response.json()
    except requests.exceptions.ConnectionError:
        print("Error: Cannot connect to Chrome.")
        print("\nMake sure Chrome is running with remote debugging:")
        print('  /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome --remote-debugging-port=9222')
        sys.exit(1)


def find_tab(tabs, url_pattern):
    """Find a tab matching the given URL pattern."""
    for tab in tabs:
        if url_pattern in tab.get("url", ""):
            return tab
    return None


class BrowserTab:
    """Control a Chrome tab via DevTools Protocol."""

    def __init__(self, ws_url):
        self.ws_url = ws_url
        self.ws = None
        self.msg_id = 0

    async def connect(self):
        self.ws = await websockets.connect(self.ws_url, max_size=None)

    async def send_command(self, method, params=None):
        """Send a CDP command and wait for response."""
        self.msg_id += 1
        msg = {"id": self.msg_id, "method": method, "params": params or {}}
        await self.ws.send(json.dumps(msg))

        while True:
            response = await self.ws.recv()
            data = json.loads(response)
            if data.get("id") == self.msg_id:
                return data.get("result", {})

    async def evaluate(self, expression):
        """Execute JavaScript in the page context."""
        result = await self.send_command("Runtime.evaluate", {
            "expression": expression,
            "returnByValue": True,
            "awaitPromise": True
        })
        return result.get("result", {}).get("value")

    async def close(self):
        if self.ws:
            await self.ws.close()


class ChatGPTController:
    """Controller for ChatGPT tab."""

    def __init__(self, tab: BrowserTab):
        self.tab = tab

    async def send_message(self, message):
        """Type a message and send it to ChatGPT."""
        # Escape the message for JavaScript
        escaped = json.dumps(message)

        # Find the input field and set its value
        await self.tab.evaluate(f"""
            (async () => {{
                // Find the contenteditable div or textarea
                const editor = document.querySelector('#prompt-textarea') ||
                               document.querySelector('[data-id="root"]') ||
                               document.querySelector('textarea');
                if (editor) {{
                    editor.focus();
                    // Clear existing content
                    editor.innerHTML = '';
                    // Set new content
                    if (editor.tagName === 'TEXTAREA') {{
                        editor.value = {escaped};
                        editor.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    }} else {{
                        editor.innerText = {escaped};
                        editor.dispatchEvent(new InputEvent('input', {{ bubbles: true }}));
                    }}
                }}
            }})()
        """)

        # Small delay to let the UI update
        await asyncio.sleep(0.5)

        # Click the send button
        await self.tab.evaluate("""
            (async () => {
                const sendBtn = document.querySelector('[data-testid="send-button"]') ||
                               document.querySelector('button[aria-label*="Send"]') ||
                               document.querySelector('form button[type="submit"]');
                if (sendBtn && !sendBtn.disabled) {
                    sendBtn.click();
                }
            })()
        """)

    async def wait_for_response(self, timeout=120):
        """Wait for ChatGPT to finish responding."""
        start_time = time.time()

        while time.time() - start_time < timeout:
            # Check if still generating
            is_generating = await self.tab.evaluate("""
                (() => {
                    // Check for stop button (indicates generating)
                    const stopBtn = document.querySelector('[data-testid="stop-button"]') ||
                                   document.querySelector('button[aria-label*="Stop"]');
                    return stopBtn !== null;
                })()
            """)

            if not is_generating:
                # Wait a bit more for the response to fully render
                await asyncio.sleep(1)
                break

            await asyncio.sleep(2)

        return await self.get_last_response()

    async def get_last_response(self):
        """Get the last assistant response."""
        return await self.tab.evaluate("""
            (() => {
                // Get all assistant messages
                const messages = document.querySelectorAll('[data-message-author-role="assistant"]');
                if (messages.length > 0) {
                    const lastMsg = messages[messages.length - 1];
                    // Get the text content from the message
                    const content = lastMsg.querySelector('.markdown') || lastMsg;
                    return content.innerText.trim();
                }
                return '';
            })()
        """)


class GeminiController:
    """Controller for Gemini tab."""

    def __init__(self, tab: BrowserTab):
        self.tab = tab

    async def send_message(self, message):
        """Type a message and send it to Gemini."""
        escaped = json.dumps(message)

        # Find and fill the input
        await self.tab.evaluate(f"""
            (async () => {{
                // Gemini uses a rich text editor
                const editor = document.querySelector('.ql-editor') ||
                               document.querySelector('[contenteditable="true"]') ||
                               document.querySelector('textarea');
                if (editor) {{
                    editor.focus();
                    if (editor.tagName === 'TEXTAREA') {{
                        editor.value = {escaped};
                        editor.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    }} else {{
                        editor.innerHTML = '';
                        editor.innerText = {escaped};
                        editor.dispatchEvent(new InputEvent('input', {{ bubbles: true }}));
                    }}
                }}
            }})()
        """)

        await asyncio.sleep(0.5)

        # Click send button
        await self.tab.evaluate("""
            (async () => {
                const sendBtn = document.querySelector('[aria-label*="Send"]') ||
                               document.querySelector('button[mat-icon-button][aria-label*="Send"]') ||
                               document.querySelector('.send-button') ||
                               document.querySelector('button.send-button');
                if (sendBtn) {
                    sendBtn.click();
                }
            })()
        """)

    async def wait_for_response(self, timeout=120):
        """Wait for Gemini to finish responding."""
        start_time = time.time()

        # Wait for response to start
        await asyncio.sleep(2)

        while time.time() - start_time < timeout:
            # Check if still generating (look for loading indicators)
            is_generating = await self.tab.evaluate("""
                (() => {
                    // Check for loading/streaming indicators
                    const loading = document.querySelector('.loading-indicator') ||
                                   document.querySelector('[aria-label*="Stop"]') ||
                                   document.querySelector('.response-streaming');
                    // Also check for cursor blinking in response
                    const cursor = document.querySelector('.cursor-blink');
                    return loading !== null || cursor !== null;
                })()
            """)

            if not is_generating:
                await asyncio.sleep(1)
                break

            await asyncio.sleep(2)

        return await self.get_last_response()

    async def get_last_response(self):
        """Get the last response from Gemini."""
        return await self.tab.evaluate("""
            (() => {
                // Get model response containers
                const responses = document.querySelectorAll('.model-response-text') ||
                                 document.querySelectorAll('[data-content-type="response"]');

                // Try different selectors for Gemini's response
                let allResponses = document.querySelectorAll('.model-response-text');
                if (allResponses.length === 0) {
                    allResponses = document.querySelectorAll('.response-content');
                }
                if (allResponses.length === 0) {
                    // Try to find by structure - responses usually have markdown
                    allResponses = document.querySelectorAll('[class*="response"] .markdown-content');
                }
                if (allResponses.length === 0) {
                    // Generic fallback
                    allResponses = document.querySelectorAll('message-content');
                }

                if (allResponses.length > 0) {
                    return allResponses[allResponses.length - 1].innerText.trim();
                }
                return '';
            })()
        """)


async def run_debate(initial_prompt, num_rounds=5, delay_between=5):
    """Run a debate between ChatGPT and Gemini."""

    print("🔍 Finding Chrome tabs...")
    tabs = get_chrome_tabs()

    chatgpt_tab_info = find_tab(tabs, "chatgpt.com")
    gemini_tab_info = find_tab(tabs, "gemini.google.com")

    if not chatgpt_tab_info:
        print("Error: ChatGPT tab not found. Please open https://chatgpt.com")
        sys.exit(1)

    if not gemini_tab_info:
        print("Error: Gemini tab not found. Please open https://gemini.google.com/app")
        sys.exit(1)

    print(f"✓ Found ChatGPT tab: {chatgpt_tab_info['url']}")
    print(f"✓ Found Gemini tab: {gemini_tab_info['url']}")

    # Connect to tabs
    chatgpt_browser = BrowserTab(chatgpt_tab_info["webSocketDebuggerUrl"])
    gemini_browser = BrowserTab(gemini_tab_info["webSocketDebuggerUrl"])

    await chatgpt_browser.connect()
    await gemini_browser.connect()

    chatgpt = ChatGPTController(chatgpt_browser)
    gemini = GeminiController(gemini_browser)

    print(f"\n{'='*60}")
    print("Starting AI Debate!")
    print(f"{'='*60}\n")

    current_message = initial_prompt

    try:
        for round_num in range(num_rounds):
            # ChatGPT's turn
            print(f"\n--- Round {round_num + 1}: ChatGPT ---")
            print(f"Sending: {current_message[:100]}..." if len(current_message) > 100 else f"Sending: {current_message}")

            await chatgpt.send_message(current_message)
            chatgpt_response = await chatgpt.wait_for_response()

            print(f"\nChatGPT says:\n{chatgpt_response[:500]}..." if len(chatgpt_response) > 500 else f"\nChatGPT says:\n{chatgpt_response}")

            if not chatgpt_response:
                print("Warning: Empty response from ChatGPT")
                break

            await asyncio.sleep(delay_between)

            # Gemini's turn
            print(f"\n--- Round {round_num + 1}: Gemini ---")

            # Frame the response as coming from ChatGPT
            gemini_prompt = f"ChatGPT just said the following. Please respond and continue the discussion:\n\n{chatgpt_response}"
            print(f"Sending: {gemini_prompt[:100]}...")

            await gemini.send_message(gemini_prompt)
            gemini_response = await gemini.wait_for_response()

            print(f"\nGemini says:\n{gemini_response[:500]}..." if len(gemini_response) > 500 else f"\nGemini says:\n{gemini_response}")

            if not gemini_response:
                print("Warning: Empty response from Gemini")
                break

            # Prepare next round
            current_message = f"Gemini responded with the following. Please continue the discussion:\n\n{gemini_response}"

            await asyncio.sleep(delay_between)

    finally:
        await chatgpt_browser.close()
        await gemini_browser.close()

    print(f"\n{'='*60}")
    print("Debate complete!")
    print(f"{'='*60}")


async def single_send(target, message):
    """Send a single message to either ChatGPT or Gemini."""

    tabs = get_chrome_tabs()

    if target == "chatgpt":
        tab_info = find_tab(tabs, "chatgpt.com")
        if not tab_info:
            print("Error: ChatGPT tab not found")
            sys.exit(1)

        browser = BrowserTab(tab_info["webSocketDebuggerUrl"])
        await browser.connect()
        controller = ChatGPTController(browser)
    else:
        tab_info = find_tab(tabs, "gemini.google.com")
        if not tab_info:
            print("Error: Gemini tab not found")
            sys.exit(1)

        browser = BrowserTab(tab_info["webSocketDebuggerUrl"])
        await browser.connect()
        controller = GeminiController(browser)

    try:
        print(f"Sending message to {target}...")
        await controller.send_message(message)
        print("Waiting for response...")
        response = await controller.wait_for_response()
        print(f"\nResponse:\n{response}")
        return response
    finally:
        await browser.close()


def main():
    parser = argparse.ArgumentParser(
        description="Control ChatGPT and Gemini from the terminal",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start a debate
  python3 ai_debate.py debate "Which is better: tabs or spaces?"

  # Run more rounds with longer delays
  python3 ai_debate.py debate "Discuss the future of AI" --rounds 10 --delay 10

  # Send a single message to ChatGPT
  python3 ai_debate.py send chatgpt "Hello, how are you?"

  # Send a single message to Gemini
  python3 ai_debate.py send gemini "What is the meaning of life?"
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Debate command
    debate_parser = subparsers.add_parser("debate", help="Start a debate between ChatGPT and Gemini")
    debate_parser.add_argument("prompt", help="Initial prompt to start the debate")
    debate_parser.add_argument("--rounds", "-r", type=int, default=5, help="Number of back-and-forth rounds (default: 5)")
    debate_parser.add_argument("--delay", "-d", type=int, default=5, help="Seconds to wait between messages (default: 5)")

    # Send command
    send_parser = subparsers.add_parser("send", help="Send a single message")
    send_parser.add_argument("target", choices=["chatgpt", "gemini"], help="Which AI to send to")
    send_parser.add_argument("message", help="Message to send")

    args = parser.parse_args()

    if args.command == "debate":
        asyncio.run(run_debate(args.prompt, args.rounds, args.delay))
    elif args.command == "send":
        asyncio.run(single_send(args.target, args.message))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
