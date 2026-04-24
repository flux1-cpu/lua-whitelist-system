from flask import Flask, request
import sqlite3
import os
from datetime import datetime

app = Flask(__name__)

conn = sqlite3.connect('whitelist.db', check_same_thread=False)
c = conn.cursor()

@app.route('/api/loadstring/<key>')
def loadstring_endpoint(key):
    c.execute("SELECT discord_id, expires_at, script_name FROM users WHERE key = ?", (key,))
    user = c.fetchone()
    
    if not user:
        return "Invalid key!", 401
    
    if user[1]:
        expires = datetime.fromisoformat(user[1])
        if expires < datetime.now():
            return "Your whitelist has expired!", 401
    
    return f"""
    -- GrimHub Script for {user[0]}
    print("✅ Loaded! Licensed to: {user[0]}")
    -- YOUR SCRIPT HERE
    """

@app.route('/health')
def health():
    return {"status": "ok"}, 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
