#!/bin/bash

echo "🎬 Ultimate Video Downloader Bot - Auto Installer"
echo "=================================================="

# Update Termux
echo "📦 Updating packages..."
pkg update -y && pkg upgrade -y

# Install dependencies
echo "🔧 Installing dependencies..."
pkg install -y python python-pip git ffmpeg sqlite termux-api

# Setup storage
echo "💾 Setting up storage..."
termux-setup-storage

# Create directory
mkdir -p ~/ultimate_bot
cd ~/ultimate_bot

# Create virtual environment
echo "🐍 Creating Python environment..."
python -m venv venv
source venv/bin/activate

# Install Python packages
echo "📥 Installing Python packages..."
pip install --upgrade pip
pip install python-telegram-bot yt-dlp requests aiohttp flask aiosqlite aiohttp-cors

echo ""
echo "✅ Installation Complete!"
echo ""
echo "📝 NEXT STEPS:"
echo "1. Get bot token from @BotFather"
echo "2. Edit bot.py: nano bot.py"
echo "3. Replace YOUR_BOT_TOKEN_HERE with your token"
echo "4. Replace ADMIN_ID with your Telegram ID"
echo "5. Run: ./start.sh"
echo ""
echo "📊 Dashboard will be at: http://localhost:5000"
