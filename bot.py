import logging
import os
import sqlite3
import re
import threading
import time
from datetime import datetime
from flask import Flask
import yt_dlp
import telegram
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

# ============ CONFIG ============
TOKEN = os.environ.get("TOKEN", "8654529573:AAHcPpsJ-YCRBJP-ZhrVmtrauhrQGq0HcQ0")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "7973440858"))
DB_PATH = "/tmp/bot.db"
DOWNLOAD_PATH = "/tmp/downloads"

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ============ FLASK (Keep Render Alive) ============
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot running!"

@app.route('/health')
def health():
    return {"status": "ok"}

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, threaded=True)

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

def download_video(url):
    import os
    os.makedirs(DOWNLOAD_PATH, exist_ok=True)
    opts = {
        'quiet': True,
        'no_warnings': True,
        'outtmpl': f'{DOWNLOAD_PATH}/%(title)s.%(ext)s',
        'format': 'best[filesize<50M]'
    }
    try:
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
    except Exception as e:
        logger.error(f"Download error: {e}")
        raise e

# ============ HANDLERS ============
def start(update, context):
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
    
    update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

def handle_link(update, context):
    user = update.effective_user
    url = update.message.text.strip()
    
    if not url.startswith('http'):
        update.message.reply_text("Send a valid URL starting with http")
        return
    
    platform = detect_platform(url)
    if not platform:
        update.message.reply_text("Unsupported platform")
        return
    
    msg = update.message.reply_text(f"Downloading from {platform}...")
    
    try:
        result = download_video(url)
        
        size = os.path.getsize(result['file'])
        if size > 50 * 1024 * 1024:
            msg.edit_text("File too big (max 50MB)")
            os.remove(result['file'])
            return
        
        with open(result['file'], 'rb') as f:
            update.message.reply_video(
                video=f,
                caption=f"{result['title']}\nBy: {result['uploader']}\nNo watermark!"
            )
        
        db.log_download(user.id, platform, url)
        msg.delete()
        os.remove(result['file'])
        
    except Exception as e:
        msg.edit_text(f"Error: {str(e)[:200]}\nCheck if video is public!")
        db.log_download(user.id, platform, url, success=False)

def stats_cmd(update, context):
    s = db.get_stats()
    update.message.reply_text(f"Users: {s['users']}\nDownloads: {s['downloads']}")

def help_cmd(update, context):
    update.message.reply_text("How to use:\n1. Copy video link\n2. Paste here\n3. Wait for download")

def button_handler(update, context):
    query = update.callback_query
    query.answer()
    if query.data == 'stats':
        stats_cmd(update, context)
    elif query.data == 'help':
        help_cmd(update, context)

# ============ MAIN ============
def main():
    # Start Flask in background (keeps Render alive)
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # Use OLD style Updater (v13 compatible)
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher
    
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("stats", stats_cmd))
    dp.add_handler(CommandHandler("help", help_cmd))
    dp.add_handler(CallbackQueryHandler(button_handler))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_link))
    
    logger.info("Bot started!")
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
