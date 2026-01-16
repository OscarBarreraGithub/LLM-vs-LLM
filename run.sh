#!/bin/bash
#
# AI Debate Tool - One-command launcher
#
# Usage:
#   ./run.sh          # Launch web interface (default)
#   ./run.sh --cli    # Launch terminal interface
#

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CHROME_PORT=9222
CHROME_DATA_DIR="/tmp/chrome-debug"
WEB_PORT=5050

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}"
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║               AI DEBATE TOOL                              ║"
echo "║         ChatGPT vs Gemini Arena                           ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Check for dependencies
check_deps() {
    echo -e "${YELLOW}Checking dependencies...${NC}"

    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}Error: python3 not found${NC}"
        exit 1
    fi

    python3 -c "import websockets" 2>/dev/null || {
        echo -e "${YELLOW}Installing websockets...${NC}"
        pip install websockets
    }

    python3 -c "import requests" 2>/dev/null || {
        echo -e "${YELLOW}Installing requests...${NC}"
        pip install requests
    }

    python3 -c "import flask" 2>/dev/null || {
        echo -e "${YELLOW}Installing flask...${NC}"
        pip install flask
    }

    echo -e "${GREEN}✓ Dependencies OK${NC}"
}

# Check if Chrome debug port is responding
chrome_is_ready() {
    curl -s "http://localhost:${CHROME_PORT}/json/version" > /dev/null 2>&1
}

# Launch Chrome with debugging
launch_chrome() {
    echo -e "${YELLOW}Launching Chrome with remote debugging...${NC}"

    # Check if Chrome is already running with debug port
    if chrome_is_ready; then
        echo -e "${GREEN}✓ Chrome already running with debug port${NC}"
        return 0
    fi

    # Check if Chrome is running without debug port
    if pgrep -x "Google Chrome" > /dev/null; then
        echo -e "${YELLOW}Chrome is running but without debug port.${NC}"
        echo -e "${YELLOW}Please close Chrome (Cmd+Q) and run this script again,${NC}"
        echo -e "${YELLOW}or manually restart Chrome with:${NC}"
        echo ""
        echo "  /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \\"
        echo "    --remote-debugging-port=${CHROME_PORT} \\"
        echo "    --user-data-dir=\"${CHROME_DATA_DIR}\""
        echo ""
        read -p "Would you like me to kill Chrome and restart it? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            pkill -9 "Google Chrome" 2>/dev/null || true
            sleep 2
        else
            exit 1
        fi
    fi

    # Launch Chrome
    /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
        --remote-debugging-port=${CHROME_PORT} \
        --remote-allow-origins=* \
        --user-data-dir="${CHROME_DATA_DIR}" \
        "https://chatgpt.com" \
        "https://gemini.google.com/app" \
        > /dev/null 2>&1 &

    echo -e "${YELLOW}Waiting for Chrome to start...${NC}"

    # Wait for Chrome to be ready
    for i in {1..30}; do
        if chrome_is_ready; then
            echo -e "${GREEN}✓ Chrome is ready${NC}"
            return 0
        fi
        sleep 1
    done

    echo -e "${RED}Error: Chrome failed to start with debug port${NC}"
    exit 1
}

# Check if AI tabs are open
check_tabs() {
    echo -e "${YELLOW}Checking for AI tabs...${NC}"

    local tabs=$(curl -s "http://localhost:${CHROME_PORT}/json")

    local has_chatgpt=$(echo "$tabs" | grep -c "chatgpt.com" || true)
    local has_gemini=$(echo "$tabs" | grep -c "gemini.google.com" || true)

    if [ "$has_chatgpt" -eq 0 ]; then
        echo -e "${YELLOW}Opening ChatGPT tab...${NC}"
        # Open via Chrome
        curl -s "http://localhost:${CHROME_PORT}/json/new?https://chatgpt.com" > /dev/null
        sleep 2
    else
        echo -e "${GREEN}✓ ChatGPT tab found${NC}"
    fi

    if [ "$has_gemini" -eq 0 ]; then
        echo -e "${YELLOW}Opening Gemini tab...${NC}"
        curl -s "http://localhost:${CHROME_PORT}/json/new?https://gemini.google.com/app" > /dev/null
        sleep 2
    else
        echo -e "${GREEN}✓ Gemini tab found${NC}"
    fi
}

# Main
main() {
    check_deps
    launch_chrome
    check_tabs

    echo ""
    echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"

    if [ "$1" == "--cli" ]; then
        echo -e "${GREEN}Starting terminal interface...${NC}"
        echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
        echo ""
        cd "$SCRIPT_DIR"
        python3 debate.py
    else
        echo -e "${GREEN}Starting web interface...${NC}"
        echo -e "${GREEN}Opening http://localhost:${WEB_PORT} in your browser${NC}"
        echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
        echo ""
        cd "$SCRIPT_DIR"
        # Open browser after a short delay (in background)
        (sleep 2 && open "http://localhost:${WEB_PORT}") &
        python3 web_app.py
    fi
}

main "$@"
