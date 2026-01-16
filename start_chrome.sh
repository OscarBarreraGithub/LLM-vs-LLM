#!/bin/bash
# Start Chrome with remote debugging enabled
# Run this script, then open ChatGPT and Gemini tabs

echo "Starting Chrome with remote debugging on port 9222..."
echo "Once Chrome opens, navigate to:"
echo "  1. https://chatgpt.com"
echo "  2. https://gemini.google.com/app"
echo ""
echo "Then run: python3 ai_debate.py debate \"Your debate topic here\""
echo ""

/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222
