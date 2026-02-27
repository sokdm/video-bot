import logging
import os
import sqlite3
import asyncio
import re
import threading
from datetime import datetime
from flask import Flask
import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, CallbackQueryHandler, filters

# ============ CONFIG ============
TOKEN = os.environ.get("TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))

if not TOKEN:
    raise ValueError("No TOKEN environment variable set!")

DB_PATH = "/tmp/bot.db"
DOWNLOAD_PATH = "/tmp/downloads"

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ============ FLASK APP ============
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "Bot is running!"

@flask_app.route('/health')
def health():
    return {"status": "alive"}

# ============ DATABASE ============
class Database:
    def __init__(self):
        self.init_db()
    
    def init_db(self):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users 
                     (user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, 
                      joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP, total_downloads INTEGER DEFAULT 0)''')
        c.execute('''CREATE TABLE IF NOT EXISTS downloads 
                     (id INTEGER PRIMARY KEY, user_id INTEGER, platform TEXT, url TEXT, 
                      download_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP, success INTEGER DEFAULT 1)''')
        conn.commit()
        conn.close()
    
    def add_user(self, user):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)', 
                  (user.id, user.username, user.first_name))
        conn.commit()
        conn.close()
    
    def log_download(self, user_id, platform, url, success=True):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('INSERT INTO downloads (user_id, platform, url, success) VALUES (?, ?, ?, ?)', 
                  (user_id, platform, url, 1 if success else 0))
        c.execute('UPDATE users SET total_downloads = total_downloads + 1 WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
    
    def get_stats(self):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM users")
        users = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM downloads WHERE success=1")
        downloads = c.fetchone()[0]
        conn.close()
        return {'users': users, 'downloads': downloads}

db = Database()

PLATFORMS = {
    'tiktok': [r'tiktok\.com', r'vm\.tiktok\.com'],
    'instagram': [r'instagram\.com/reel', r'instagr\.am'],
    'youtube': [r'youtube\.com/shorts', r'youtu\.be'],
    'twitter': [r'twitter\.com', r'x\.com'],
    'facebook': [r'facebook\.com', r'fb\.watch']
}

def detect_platform(url):
    url_lower = url.lower()
    for plat, patterns in PLATFORMS.items():
        if any(re.search(p, url_lower) for p in patterns):
            return plat
    return None

async def download_video(url):
    os.makedirs(DOWNLOAD_PATH, exist_ok=True)
    opts = {
        'quiet': True,
        'no_warnings': True,
        'outtmpl': f'{DOWNLOAD_PATH}/%(title)s.%(ext)s',
        'format': 'best[filesize<50M]'
    }
    try:
        loop = asyncio.get_event_loop()
        def _dl():
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                if not os.path.exists(filename):
                    base = os.path.splitext(filename)[0]
                    for ext in ['.mp4', '.mkv', '.webm']:
                        if os.path.exists(base + ext):
                            filename = base + ext
                            break
                return {
                    'file': filename,
                    'title': info.get('title', 'Video')[:100],
                    'uploader': info.get('uploader', 'Unknown'),
                    'duration': info.get('duration', 0)
                }
        return await loop.run_in_executor(None, _dl)
    except Exception as e:
        logger.error(f"Download error: {e}")
        raise e

# ============ HANDLERS ============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.add_user(user)
    
    keyboard = [
        [InlineKeyboardButton("Stats", callback_data='stats')],
        [InlineKeyboardButton("Help", callback_data='help')]
    ]
    
    text = f"""Welcome {user.first_name}!

Send me video links from:
TikTok (no watermark!)
Instagram Reels
YouTube Shorts  
Twitter/X
Facebook

Just paste the link!"""
    
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    url = update.message.text.strip()
    
    if not url.startswith('http'):
        await update.message.reply_text("Send a valid URL starting with http")
        return
    
    platform = detect_platform(url)
    if not platform:
        await update.message.reply_text("Unsupported platform")
        return
    
    msg = await update.message.reply_text(f"Downloading from {platform}...")
    
    try:
        result = await download_video(url)
        
        size = os.path.getsize(result['file'])
        if size > 50 * 1024 * 1024:
            await msg.edit_text("File too big (max 50MB)")
            os.remove(result['file'])
            return
        
        with open(result['file'], 'rb') as f:
            await update.message.reply_video(
                video=f,
                caption=f"{result['title']}\nBy: {result['uploader']}\nNo watermark!"
            )
        
        db.log_download(user.id, platform, url)
        await msg.delete()
        os.remove(result['file'])
        
    except Exception as e:
        await msg.edit_text(f"Error: {str(e)[:200]}\nCheck if video is public!")
        db.log_download(user.id, platform, url, success=False)

async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    s = db.get_stats()
    await update.message.reply_text(f"Users: {s['users']}\nDownloads: {s['downloads']}")

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("How to use:\n1. Copy video link\n2. Paste here\n3. Wait for download")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == 'stats':
        await stats_cmd(update, context)
    elif query.data == 'help':
        await help_cmd(update, context)

# ============ MAIN ============
def main():
    # Create application
    application = Application.builder().token(TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stats", stats_cmd))
    application.add_handler(CommandHandler("help", help_cmd))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))
    
    # Start bot in background thread
    def run_bot():
        application.run_polling(drop_pending_updates=True)
    
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    logger.info("Bot started in background")
    
    # Start Flask (keeps Render alive)
    port = int(os.environ.get("PORT", 10000))
    logger.info(f"Starting web server on port {port}")
    flask_app.run(host='0.0.0.0', port=port)

if __name__ == '__main__':
    main()
