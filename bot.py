import discord
from discord.ext import commands
import sqlite3
import secrets
import os
from datetime import datetime, timedelta

# Database setup
conn = sqlite3.connect('whitelist.db')
c = conn.cursor()

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
conn.commit()

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='/', intents=intents)

def is_admin():
    async def predicate(interaction: discord.Interaction):
        return interaction.user.guild_permissions.administrator
    return commands.check(predicate)

class UserPanel(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=None)
        self.user_id = user_id
    
    @discord.ui.button(label="Get Script", style=discord.ButtonStyle.success, emoji="📜")
    async def script_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ Not your panel!", ephemeral=True)
            return
        
        c.execute("SELECT key, expires_at, script_name FROM users WHERE discord_id = ?", (self.user_id,))
        user = c.fetchone()
        
        if not user or not user[0]:
            await interaction.response.send_message("❌ You are not whitelisted! Contact an admin.", ephemeral=True)
            return
        
        if user[1]:
            expires = datetime.fromisoformat(user[1])
            if expires < datetime.now():
                await interaction.response.send_message("❌ Your whitelist has expired! Contact an admin to renew.", ephemeral=True)
                return
        
        script_name = user[2] if user[2] else "main"
        url = f"https://YOUR_RAILWAY_URL.up.railway.app/api/loadstring/{user[0]}"
        
        await interaction.response.send_message(
            f"```lua\nloadstring(game:HttpGet('{url}'))()\n```\n"
            f"📁 Script: **{script_name}**\n"
            f"⏰ Expires: {user[1][:10] if user[1] else 'Never'}",
            ephemeral=True
        )
    
    @discord.ui.button(label="Reset HWID", style=discord.ButtonStyle.danger, emoji="🔄")
    async def reset_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ Not your panel!", ephemeral=True)
            return
        
        c.execute("UPDATE users SET hwid = NULL WHERE discord_id = ?", (self.user_id,))
        conn.commit()
        await interaction.response.send_message("✅ HWID reset! You can now use your key on a new PC.", ephemeral=True)
    
    @discord.ui.button(label="My Info", style=discord.ButtonStyle.secondary, emoji="ℹ️")
    async def info_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ Not your panel!", ephemeral=True)
            return
        
        c.execute("SELECT redeem_count, created_at, expires_at, script_name FROM users WHERE discord_id = ?", (self.user_id,))
        user = c.fetchone()
        
        if user:
            embed = discord.Embed(title="📊 Your Whitelist Info", color=0x5865F2)
            embed.add_field(name="Script", value=user[3] if user[3] else "main", inline=True)
            embed.add_field(name="Redeems", value=str(user[0]), inline=True)
            embed.add_field(name="Created", value=user[1][:10] if user[1] else "N/A", inline=True)
            embed.add_field(name="Expires", value=user[2][:10] if user[2] else "Never", inline=True)
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message("❌ No info found!", ephemeral=True)

@bot.tree.command(name="panel", description="Open your user panel")
async def panel(interaction: discord.Interaction):
    """Open user panel (any user can use this)"""
    embed = discord.Embed(
        title="🔐 GrimHub User Panel",
        description="Click the buttons below to get your script or reset HWID.",
        color=0x5865F2
    )
    await interaction.response.send_message(embed=embed, view=UserPanel(str(interaction.user.id)))

@bot.tree.command(name="whitelist", description="Whitelist a user (Admin only)")
@is_admin()
async def whitelist(interaction: discord.Interaction, user: discord.User, time: str, script: str):
    """
    Whitelist a user with expiration time and script name
    
    Time formats:
    - 7d = 7 days
    - 30d = 30 days
    - 1m = 1 month
    - 1y = 1 year
    - never = never expires
    """
    
    # Parse time
    if time.lower() == "never":
        expires_at = None
        expires_readable = "Never"
    else:
        amount = int(time[:-1])
        unit = time[-1].lower()
        
        if unit == 'd':
            expires = datetime.now() + timedelta(days=amount)
        elif unit == 'm':
            expires = datetime.now() + timedelta(days=amount * 30)
        elif unit == 'y':
            expires = datetime.now() + timedelta(days=amount * 365)
        else:
            await interaction.response.send_message("❌ Invalid time format! Use: 7d, 30d, 1m, 1y, never", ephemeral=True)
            return
        
        expires_at = expires.isoformat()
        expires_readable = expires.strftime("%Y-%m-%d")
    
    # Generate key
    key = f"{secrets.token_hex(4).upper()}-{secrets.token_hex(4).upper()}-{secrets.token_hex(4).upper()}"
    
    # Add to database
    c.execute("INSERT OR REPLACE INTO users (discord_id, key, redeem_count, created_at, expires_at, script_name) VALUES (?, ?, ?, ?, ?, ?)",
              (str(user.id), key, 0, datetime.now().isoformat(), expires_at, script))
    
    c.execute("INSERT OR REPLACE INTO keys (key, discord_id, used, created_at, expires_at, script_name) VALUES (?, ?, ?, ?, ?, ?)",
              (key, str(user.id), False, datetime.now().isoformat(), expires_at, script))
    conn.commit()
    
    # Try to DM the user
    embed = discord.Embed(
        title="✅ You have been whitelisted!",
        description=f"**Script:** {script}\n**Expires:** {expires_readable}",
        color=0x00ff00
    )
    try:
        await user.send(embed=embed)
        await user.send("Use `/panel` in the server to get your script!")
    except:
        pass
    
    await interaction.response.send_message(
        f"✅ Whitelisted {user.mention}\n"
        f"📁 Script: **{script}**\n"
        f"⏰ Expires: **{expires_readable}**\n"
        f"🔑 Key: `{key}`",
        ephemeral=True
    )

@bot.tree.command(name="gen", description="Generate keys (Admin only)")
@is_admin()
async def gen(interaction: discord.Interaction, amount: int = 1):
    keys = []
    for _ in range(amount):
        key = f"{secrets.token_hex(4).upper()}-{secrets.token_hex(4).upper()}-{secrets.token_hex(4).upper()}"
        c.execute("INSERT INTO keys (key, used, created_at) VALUES (?, ?, ?)", (key, False, datetime.now().isoformat()))
        keys.append(key)
    conn.commit()
    await interaction.response.send_message(f"✅ Generated {amount} key(s):\n```\n" + "\n".join(keys) + "\n```", ephemeral=True)

@bot.tree.command(name="keys", description="List all unused keys (Admin only)")
@is_admin()
async def keys(interaction: discord.Interaction):
    c.execute("SELECT key FROM keys WHERE used = FALSE")
    keys = c.fetchall()
    if keys:
        await interaction.response.send_message(f"📋 Unused keys:\n```\n" + "\n".join([k[0] for k in keys]) + "\n```", ephemeral=True)
    else:
        await interaction.response.send_message("No unused keys!", ephemeral=True)

@bot.tree.command(name="total", description="Show total users (Admin only)")
@is_admin()
async def total(interaction: discord.Interaction):
    c.execute("SELECT COUNT(*) FROM users")
    count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users WHERE expires_at IS NOT NULL AND expires_at < datetime('now')")
    expired = c.fetchone()[0]
    
    embed = discord.Embed(title="📊 GrimHub Stats", color=0x5865F2)
    embed.add_field(name="Total Users", value=str(count), inline=True)
    embed.add_field(name="Expired", value=str(expired), inline=True)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="unwhitelist", description="Remove a user from whitelist (Admin only)")
@is_admin()
async def unwhitelist(interaction: discord.Interaction, user: discord.User):
    c.execute("DELETE FROM users WHERE discord_id = ?", (str(user.id),))
    c.execute("DELETE FROM hwid_locks WHERE discord_id = ?", (str(user.id),))
    conn.commit()
    
    await interaction.response.send_message(f"✅ Removed {user.mention} from whitelist!", ephemeral=True)

@bot.event
async def on_ready():
    print(f"✅ Bot online! Logged in as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Error syncing: {e}")

bot.run(os.environ.get("DISCORD_TOKEN"))
