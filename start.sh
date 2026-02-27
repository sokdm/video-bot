#!/bin/bash

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

cd ~/ultimate_bot
source venv/bin/activate

echo -e "${GREEN}🚀 Ultimate Video Downloader Bot${NC}"
echo "=================================="

# Check if token is set
if grep -q "YOUR_BOT_TOKEN_HERE" bot.py; then
    echo -e "${RED}❌ ERROR: Please edit bot.py and set your BOT TOKEN!${NC}"
    echo "Get token from @BotFather on Telegram"
    exit 1
fi

# Create directories
mkdir -p downloads logs

echo -e "${YELLOW}📊 Starting Dashboard on http://localhost:5000${NC}"
python dashboard.py > logs/dashboard.log 2>&1 &
DASHBOARD_PID=$!
echo $DASHBOARD_PID > .dashboard.pid

sleep 2

echo -e "${YELLOW}🤖 Starting Telegram Bot...${NC}"
python bot.py

# Cleanup on exit
kill $DASHBOARD_PID 2>/dev/null
rm -f .dashboard.pid
