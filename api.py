from flask import Flask, request
import sqlite3
import os
from datetime import datetime

app = Flask(__name__)

conn = sqlite3.connect('whitelist.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS users (discord_id TEXT PRIMARY KEY, key TEXT, hwid TEXT, redeem_count INTEGER, created_at TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS keys (key TEXT PRIMARY KEY, discord_id TEXT, used BOOLEAN, created_at TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS hwid_locks (discord_id TEXT PRIMARY KEY, hwid TEXT, last_seen TEXT)''')
conn.commit()

@app.route('/api/loadstring/<key>')
def loadstring_endpoint(key):
    c.execute("SELECT discord_id FROM users WHERE key = ?", (key,))
    user = c.fetchone()
    if not user:
        return "Invalid key!", 401
    discord_id = user[0]
    hwid = request.headers.get('X-HWID', '')
    c.execute("SELECT hwid FROM hwid_locks WHERE discord_id = ?", (discord_id,))
    lock = c.fetchone()
    if lock and lock[0] and lock[0] != hwid and hwid:
        return "HWID mismatch! Use !panel and click Reset HWID", 401
    if not lock and hwid:
        c.execute("INSERT INTO hwid_locks VALUES (?, ?, ?)", (discord_id, hwid, datetime.now().isoformat()))
        conn.commit()
    return f'print("✅ GrimHub loaded! Licensed to: {discord_id}")'

@app.route('/health')
def health():
    return {"status": "ok"}, 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
