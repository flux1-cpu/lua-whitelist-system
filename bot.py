import discord
from discord.ext import commands
import sqlite3
import secrets
import os
from datetime import datetime

# Database setup
conn = sqlite3.connect('whitelist.db')
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS users
             (discord_id TEXT PRIMARY KEY, key TEXT, hwid TEXT, redeem_count INTEGER, created_at TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS keys
             (key TEXT PRIMARY KEY, discord_id TEXT, used BOOLEAN, created_at TEXT)''')
conn.commit()

# Bot setup with required intents for slash commands
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='/', intents=intents)

class ControlPanel(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=None)
        self.user_id = user_id
    
    @discord.ui.button(label="Get Script", style=discord.ButtonStyle.success, emoji="📜")
    async def script_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ Not your panel!", ephemeral=True)
            return
        c.execute("SELECT key FROM users WHERE discord_id = ?", (self.user_id,))
        user = c.fetchone()
        if user and user[0]:
            url = f"https://YOUR_RAILWAY_URL.up.railway.app/api/loadstring/{user[0]}"
            await interaction.response.send_message(
                f"```lua\nloadstring(game:HttpGet('{url}'))()\n```\n"
                f"⚠️ Make sure to replace YOUR_RAILWAY_URL with your actual Railway URL",
                ephemeral=True
            )
        else:
            await interaction.response.send_message("❌ You need a key! Ask an admin for `/gen`", ephemeral=True)
    
    @discord.ui.button(label="Reset HWID", style=discord.ButtonStyle.danger, emoji="🔄")
    async def reset_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            await interaction.response.send_message("❌ Not your panel!", ephemeral=True)
            return
        c.execute("UPDATE users SET hwid = NULL WHERE discord_id = ?", (self.user_id,))
        conn.commit()
        await interaction.response.send_message("✅ HWID reset! You can now use your key on a new PC.", ephemeral=True)

@bot.tree.command(name="panel", description="Open your control panel")
async def panel(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🔐 GrimHub Control Panel",
        description="Click the buttons below:",
        color=0x5865F2
    )
    await interaction.response.send_message(embed=embed, view=ControlPanel(str(interaction.user.id)))

@bot.tree.command(name="gen", description="Generate keys (Admin only)")
@commands.has_permissions(administrator=True)
async def gen(interaction: discord.Interaction, amount: int = 1):
    keys = []
    for _ in range(amount):
        key = f"{secrets.token_hex(4).upper()}-{secrets.token_hex(4).upper()}-{secrets.token_hex(4).upper()}"
        c.execute("INSERT INTO keys (key, used, created_at) VALUES (?, ?, ?)", (key, False, datetime.now().isoformat()))
        keys.append(key)
    conn.commit()
    await interaction.response.send_message(f"✅ Generated {amount} key(s):\n```\n" + "\n".join(keys) + "\n```", ephemeral=True)

@bot.tree.command(name="keys", description="List all unused keys (Admin only)")
@commands.has_permissions(administrator=True)
async def keys(interaction: discord.Interaction):
    c.execute("SELECT key FROM keys WHERE used = FALSE")
    keys = c.fetchall()
    if keys:
        key_list = "\n".join([k[0] for k in keys])
        await interaction.response.send_message(f"📋 Unused keys:\n```\n{key_list}\n```", ephemeral=True)
    else:
        await interaction.response.send_message("No unused keys available!", ephemeral=True)

@bot.tree.command(name="total", description="Show total users (Admin only)")
@commands.has_permissions(administrator=True)
async def total(interaction: discord.Interaction):
    c.execute("SELECT COUNT(*) FROM users")
    count = c.fetchone()[0]
    await interaction.response.send_message(f"📊 Total users: **{count}**", ephemeral=True)

@bot.tree.command(name="adduser", description="Manually add a user (Admin only)")
@commands.has_permissions(administrator=True)
async def adduser(interaction: discord.Interaction, discord_id: str, key: str):
    c.execute("INSERT OR REPLACE INTO users (discord_id, key, redeem_count, created_at) VALUES (?, ?, ?, ?)",
              (discord_id, key, 1, datetime.now().isoformat()))
    conn.commit()
    await interaction.response.send_message(f"✅ Added user {discord_id} with key {key}", ephemeral=True)

@bot.event
async def on_ready():
    print(f"✅ Bot is online! Logged in as {bot.user}")
    print(f"Bot ID: {bot.user.id}")
    print(f"Syncing slash commands...")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Error syncing commands: {e}")

bot.run(os.environ.get("DISCORD_TOKEN"))
