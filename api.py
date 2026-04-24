from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
import os
import secrets
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)  # Allow Lovable dashboard to connect

# Database setup
conn = sqlite3.connect('whitelist.db', check_same_thread=False)
c = conn.cursor()

# Create tables
c.execute('''CREATE TABLE IF NOT EXISTS users
             (discord_id TEXT PRIMARY KEY, 
              key TEXT, 
              hwid TEXT, 
              redeem_count INTEGER, 
              created_at TEXT,
              expires_at TEXT,
              script_name TEXT)''')

c.execute('''CREATE TABLE IF NOT EXISTS keys
             (key TEXT PRIMARY KEY, 
              discord_id TEXT, 
              used BOOLEAN, 
              created_at TEXT,
              expires_at TEXT,
              script_name TEXT)''')

c.execute('''CREATE TABLE IF NOT EXISTS hwid_locks
             (discord_id TEXT PRIMARY KEY, 
              hwid TEXT, 
              last_seen TEXT)''')

c.execute('''CREATE TABLE IF NOT EXISTS activity_logs
             (id INTEGER PRIMARY KEY AUTOINCREMENT, 
              action TEXT, 
              discord_id TEXT, 
              details TEXT, 
              created_at TEXT)''')
conn.commit()

# API Key for dashboard security
API_KEY = os.environ.get("DASHBOARD_API_KEY", "my-secret-key-123")

def require_auth():
    """Check if request has valid API key"""
    key = request.headers.get('X-API-Key')
    return key == API_KEY

def log_action(action, discord_id, details=""):
    """Log admin actions"""
    c.execute("INSERT INTO activity_logs (action, discord_id, details, created_at) VALUES (?, ?, ?, ?)",
              (action, discord_id, details, datetime.now().isoformat()))
    conn.commit()

# ============================================
# ROOT ENDPOINTS
# ============================================

@app.route('/')
def home():
    return "GrimHub API is running! Use /api/health to check status."

@app.route('/api/health')
def health():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}, 200

# ============================================
# LOADSTRING ENDPOINT (For Roblox)
# ============================================

@app.route('/api/loadstring/<key>')
def loadstring_endpoint(key):
    c.execute("SELECT discord_id, expires_at, script_name FROM users WHERE key = ?", (key,))
    user = c.fetchone()
    
    if not user:
        return "Invalid key! Please purchase a valid key.", 401
    
    discord_id = user[0]
    expires_at = user[1]
    script_name = user[2] if user[2] else "main"
    
    # Check expiration
    if expires_at:
        expires = datetime.fromisoformat(expires_at)
        if expires < datetime.now():
            return "Your whitelist has expired! Please renew.", 401
    
    # Get HWID from headers (sent by executor)
    hwid = request.headers.get('X-HWID', '')
    
    # HWID binding
    c.execute("SELECT hwid FROM hwid_locks WHERE discord_id = ?", (discord_id,))
    lock = c.fetchone()
    
    if lock and lock[0] and lock[0] != hwid and hwid:
        return "HWID mismatch! Use /panel in Discord to reset HWID.", 401
    
    if not lock and hwid:
        c.execute("INSERT INTO hwid_locks VALUES (?, ?, ?)", 
                  (discord_id, hwid, datetime.now().isoformat()))
        conn.commit()
    
    # Return the actual script
    return f'''-- GrimHub Protected Script
-- Licensed to Discord ID: {discord_id}
-- Script: {script_name}
-- Key: {key}

print("✅ GrimHub loaded successfully!")
print("📁 Script: {script_name}")
print("👤 Licensed to: {discord_id}")

-- ============================================
-- YOUR ACTUAL SCRIPT GOES HERE
-- ============================================

local Players = game:GetService("Players")
local lp = Players.LocalPlayer

print("Welcome to GrimHub, " .. lp.Name)

-- Create GUI (example)
local screenGui = Instance.new("ScreenGui")
screenGui.Name = "GrimHub"
screenGui.Parent = lp:WaitForChild("PlayerGui")

local frame = Instance.new("Frame")
frame.Size = UDim2.new(0, 300, 0, 200)
frame.Position = UDim2.new(0.5, -150, 0.5, -100)
frame.BackgroundColor3 = Color3.fromRGB(20, 20, 30)
frame.Parent = screenGui

local title = Instance.new("TextLabel")
title.Text = "GrimHub"
title.Size = UDim2.new(1, 0, 0, 30)
title.BackgroundTransparency = 1
title.TextColor3 = Color3.fromRGB(255, 255, 255)
title.Parent = frame

print("🚀 Script ready!")
'''

# ============================================
# DASHBOARD API ENDPOINTS
# ============================================

@app.route('/api/dashboard/stats', methods=['GET'])
def get_stats():
    if not require_auth():
        return jsonify({"error": "Unauthorized"}), 401
    
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM users WHERE expires_at IS NOT NULL AND expires_at < datetime('now')")
    expired_users = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM keys WHERE used = FALSE")
    unused_keys = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM users WHERE date(created_at) = date('now')")
    today_users = c.fetchone()[0]
    
    return jsonify({
        "total_users": total_users,
        "expired_users": expired_users,
        "active_users": total_users - expired_users,
        "unused_keys": unused_keys,
        "today_users": today_users
    })

@app.route('/api/dashboard/users', methods=['GET'])
def get_users():
    if not require_auth():
        return jsonify({"error": "Unauthorized"}), 401
    
    c.execute("""
        SELECT u.discord_id, u.key, u.redeem_count, u.created_at, u.expires_at, u.script_name, h.hwid 
        FROM users u 
        LEFT JOIN hwid_locks h ON u.discord_id = h.discord_id
    """)
    users = c.fetchall()
    
    result = []
    for u in users:
        result.append({
            "discord_id": u[0],
            "key": u[1],
            "redeem_count": u[2],
            "created_at": u[3],
            "expires_at": u[4],
            "script_name": u[5],
            "hwid_locked": u[6] is not None
        })
    return jsonify(result)

@app.route('/api/dashboard/keys', methods=['GET'])
def get_keys():
    if not require_auth():
        return jsonify({"error": "Unauthorized"}), 401
    
    c.execute("SELECT key, created_at FROM keys WHERE used = FALSE")
    keys = c.fetchall()
    
    result = [{"key": k[0], "created_at": k[1]} for k in keys]
    return jsonify(result)

@app.route('/api/dashboard/add-user', methods=['POST'])
def add_user():
    if not require_auth():
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.json
    discord_id = data.get('discord_id')
    script_name = data.get('script_name', 'main')
    duration_days = data.get('duration_days', 30)
    
    # Generate unique key
    key = f"{secrets.token_hex(4).upper()}-{secrets.token_hex(4).upper()}-{secrets.token_hex(4).upper()}"
    
    # Set expiration
    if duration_days == 0:
        expires_at = None
    else:
        expires = datetime.now() + timedelta(days=duration_days)
        expires_at = expires.isoformat()
    
    # Add to database
    c.execute("INSERT OR REPLACE INTO users (discord_id, key, redeem_count, created_at, expires_at, script_name) VALUES (?, ?, ?, ?, ?, ?)",
              (discord_id, key, 0, datetime.now().isoformat(), expires_at, script_name))
    
    c.execute("INSERT OR REPLACE INTO keys (key, discord_id, used, created_at, expires_at, script_name) VALUES (?, ?, ?, ?, ?, ?)",
              (key, discord_id, False, datetime.now().isoformat(), expires_at, script_name))
    conn.commit()
    
    log_action("add_user", discord_id, f"Script: {script_name}, Duration: {duration_days} days")
    
    return jsonify({"success": True, "key": key})

@app.route('/api/dashboard/remove-user', methods=['POST'])
def remove_user():
    if not require_auth():
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.json
    discord_id = data.get('discord_id')
    
    c.execute("DELETE FROM users WHERE discord_id = ?", (discord_id,))
    c.execute("DELETE FROM hwid_locks WHERE discord_id = ?", (discord_id,))
    conn.commit()
    
    log_action("remove_user", discord_id, "User removed")
    
    return jsonify({"success": True})

@app.route('/api/dashboard/reset-hwid', methods=['POST'])
def reset_hwid():
    if not require_auth():
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.json
    discord_id = data.get('discord_id')
    
    c.execute("UPDATE users SET hwid = NULL WHERE discord_id = ?", (discord_id,))
    c.execute("DELETE FROM hwid_locks WHERE discord_id = ?", (discord_id,))
    conn.commit()
    
    log_action("reset_hwid", discord_id, "HWID reset")
    
    return jsonify({"success": True})

@app.route('/api/dashboard/generate-keys', methods=['POST'])
def generate_keys():
    if not require_auth():
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.json
    amount = data.get('amount', 1)
    
    keys = []
    for _ in range(amount):
        key = f"{secrets.token_hex(4).upper()}-{secrets.token_hex(4).upper()}-{secrets.token_hex(4).upper()}"
        c.execute("INSERT INTO keys (key, used, created_at) VALUES (?, ?, ?)", 
                  (key, False, datetime.now().isoformat()))
        keys.append(key)
    conn.commit()
    
    log_action("generate_keys", "system", f"Generated {amount} keys")
    
    return jsonify({"success": True, "keys": keys})

@app.route('/api/dashboard/activity', methods=['GET'])
def get_activity():
    if not require_auth():
        return jsonify({"error": "Unauthorized"}), 401
    
    c.execute("SELECT action, discord_id, details, created_at FROM activity_logs ORDER BY id DESC LIMIT 50")
    logs = c.fetchall()
    
    result = [{"action": l[0], "discord_id": l[1], "details": l[2], "created_at": l[3]} for l in logs]
    return jsonify(result)

# ============================================
# RUN THE APP
# ============================================

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
