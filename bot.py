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

# Bot setup
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
                f"```lua\nloadstring(game:HttpGet('{url}'))()\n```",
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
        await interaction.response.send_message("✅ HWID reset!", ephemeral=True)

@bot.tree.command(name="panel", description="Open your control panel")
async def panel(interaction: discord.Interaction):
    embed = discord.Embed(title="🔐 GrimHub Control Panel", color=0x5865F2)
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

@bot.tree.command(name="keys", description="List unused keys (Admin only)")
@commands.has_permissions(administrator=True)
async def keys(interaction: discord.Interaction):
    c.execute("SELECT key FROM keys WHERE used = FALSE")
    keys = c.fetchall()
    if keys:
        await interaction.response.send_message(f"📋 Unused keys:\n```\n" + "\n".join([k[0] for k in keys]) + "\n```", ephemeral=True)
    else:
        await interaction.response.send_message("No unused keys!", ephemeral=True)

@bot.tree.command(name="total", description="Show total users (Admin only)")
@commands.has_permissions(administrator=True)
async def total(interaction: discord.Interaction):
    c.execute("SELECT COUNT(*) FROM users")
    count = c.fetchone()[0]
    await interaction.response.send_message(f"📊 Total users: **{count}**", ephemeral=True)

@bot.event
async def on_ready():
    print(f"✅ Bot online! Logged in as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Error syncing: {e}")

bot.run(os.environ.get("DISCORD_TOKEN"))
