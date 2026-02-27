from flask import Flask, jsonify, render_template_string
import sqlite3
from datetime import datetime, timedelta
import os

app = Flask(__name__)
DB_PATH = "bot_database.db"

DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Bot Admin Dashboard</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            min-height: 100vh;
            padding: 20px;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        h1 { text-align: center; margin-bottom: 30px; font-size: 2.5em; text-shadow: 2px 2px 4px rgba(0,0,0,0.3); }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: rgba(255,255,255,0.1);
            backdrop-filter: blur(10px);
            border-radius: 15px;
            padding: 25px;
            text-align: center;
            border: 1px solid rgba(255,255,255,0.2);
            transition: transform 0.3s;
        }
        .stat-card:hover { transform: translateY(-5px); }
        .stat-number { font-size: 3em; font-weight: bold; margin: 10px 0; }
        .stat-label { font-size: 1.1em; opacity: 0.9; }
        .section {
            background: rgba(255,255,255,0.1);
            backdrop-filter: blur(10px);
            border-radius: 15px;
            padding: 25px;
            margin-bottom: 20px;
            border: 1px solid rgba(255,255,255,0.2);
        }
        h2 { margin-bottom: 15px; color: #ffd700; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid rgba(255,255,255,0.2); }
        th { color: #ffd700; font-weight: 600; }
        tr:hover { background: rgba(255,255,255,0.05); }
        .platform-badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.85em;
            font-weight: bold;
        }
        .tiktok { background: #ff0050; }
        .instagram { background: #e4405f; }
        .youtube { background: #ff0000; }
        .twitter { background: #1da1f2; }
        .facebook { background: #1877f2; }
        .refresh-btn {
            position: fixed;
            bottom: 30px;
            right: 30px;
            background: #ffd700;
            color: #333;
            border: none;
            padding: 15px 25px;
            border-radius: 50px;
            font-weight: bold;
            cursor: pointer;
            box-shadow: 0 4px 15px rgba(0,0,0,0.3);
            transition: all 0.3s;
        }
        .refresh-btn:hover { transform: scale(1.1); }
        .live-indicator {
            display: inline-block;
            width: 10px;
            height: 10px;
            background: #00ff88;
            border-radius: 50%;
            margin-left: 10px;
            animation: pulse 2s infinite;
        }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
    </style>
</head>
<body>
    <div class="container">
        <h1>🤖 Bot Dashboard <span class="live-indicator"></span></h1>
        
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-label">Total Users</div>
                <div class="stat-number">{{ stats.total_users }}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Total Downloads</div>
                <div class="stat-number">{{ stats.total_downloads }}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Today's Users</div>
                <div class="stat-number" style="color: #00ff88;">+{{ stats.today_users }}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Today's Downloads</div>
                <div class="stat-number" style="color: #00ff88;">+{{ stats.today_downloads }}</div>
            </div>
        </div>

        <div class="section">
            <h2>🏆 Top Users</h2>
            <table>
                <tr>
                    <th>Rank</th>
                    <th>User</th>
                    <th>Downloads</th>
                    <th>Joined</th>
                </tr>
                {% for user in top_users %}
                <tr>
                    <td>#{{ loop.index }}</td>
                    <td>{{ user[2] or user[1] or 'Anonymous' }}</td>
                    <td><strong>{{ user[4] }}</strong></td>
                    <td>{{ user[5][:10] }}</td>
                </tr>
                {% endfor %}
            </table>
        </div>

        <div class="section">
            <h2>📊 Platform Distribution</h2>
            <table>
                <tr>
                    <th>Platform</th>
                    <th>Downloads</th>
                    <th>Percentage</th>
                </tr>
                {% for platform, count in stats.platforms.items() %}
                <tr>
                    <td><span class="platform-badge {{ platform }}">{{ platform.upper() }}</span></td>
                    <td>{{ count }}</td>
                    <td>{{ "%.1f"|format((count / stats.total_downloads * 100) if stats.total_downloads > 0 else 0) }}%</td>
                </tr>
                {% endfor %}
            </table>
        </div>

        <div class="section">
            <h2>🕐 Recent Downloads</h2>
            <table>
                <tr>
                    <th>Time</th>
                    <th>Platform</th>
                    <th>User ID</th>
                    <th>Status</th>
                </tr>
                {% for dl in recent_downloads %}
                <tr>
                    <td>{{ dl[4][11:16] }}</td>
                    <td><span class="platform-badge {{ dl[2] }}">{{ dl[2].upper() }}</span></td>
                    <td>{{ dl[1] }}</td>
                    <td>{{ '✅ Success' if dl[5] else '❌ Failed' }}</td>
                </tr>
                {% endfor %}
            </table>
        </div>
    </div>
    
    <button class="refresh-btn" onclick="location.reload()">🔄 Refresh</button>
    
    <script>
        setInterval(() => location.reload(), 30000); // Auto refresh every 30s
    </script>
</body>
</html>
"""

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def dashboard():
    conn = get_db()
    
    # Stats
    cursor = conn.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    
    cursor = conn.execute("SELECT COUNT(*) FROM downloads WHERE success=1")
    total_downloads = cursor.fetchone()[0]
    
    today = datetime.now().strftime('%Y-%m-%d')
    cursor = conn.execute("SELECT COUNT(*) FROM users WHERE date(joined_date) = ?", (today,))
    today_users = cursor.fetchone()[0]
    
    cursor = conn.execute("SELECT COUNT(*) FROM downloads WHERE date(download_time) = ?", (today,))
    today_downloads = cursor.fetchone()[0]
    
    cursor = conn.execute("SELECT platform, COUNT(*) FROM downloads WHERE success=1 GROUP BY platform")
    platforms = dict(cursor.fetchall())
    
    # Top users
    cursor = conn.execute('''
        SELECT user_id, username, first_name, last_name, total_downloads, joined_date 
        FROM users ORDER BY total_downloads DESC LIMIT 10
    ''')
    top_users = cursor.fetchall()
    
    # Recent downloads
    cursor = conn.execute('''
        SELECT * FROM downloads ORDER BY download_time DESC LIMIT 20
    ''')
    recent_downloads = cursor.fetchall()
    
    conn.close()
    
    stats = {
        'total_users': total_users,
        'total_downloads': total_downloads,
        'today_users': today_users,
        'today_downloads': today_downloads,
        'platforms': platforms
    }
    
    return render_template_string(DASHBOARD_HTML, stats=stats, top_users=top_users, recent_downloads=recent_downloads)

@app.route('/api/stats')
def api_stats():
    conn = get_db()
    cursor = conn.execute("SELECT * FROM stats ORDER BY date DESC LIMIT 30")
    data = cursor.fetchall()
    conn.close()
    return jsonify([dict(row) for row in data])

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
