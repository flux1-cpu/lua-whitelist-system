import discord
from discord.ext import commands
import sqlite3
import secrets
import os
from datetime import datetime

conn = sqlite3.connect('whitelist.db')
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS users (discord_id TEXT PRIMARY KEY, key TEXT, hwid TEXT, redeem_count INTEGER, created_at TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS keys (key TEXT PRIMARY KEY, discord_id TEXT, used BOOLEAN, created_at TEXT)''')
conn.commit()

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

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
            url = f"https://lua-whitelist-api.onrender.com/api/loadstring/{user[0]}"
            await interaction.response.send_message(f"```lua\nloadstring(game:HttpGet('{url}'))()\n```", ephemeral=True)
        else:
            await interaction.response.send_message("❌ You need a key! Ask an admin for !gen", ephemeral=True)

@bot.command()
async def panel(ctx):
    await ctx.send("🔐 Click below to get your script!", view=ControlPanel(str(ctx.author.id)))

@bot.command()
@commands.has_permissions(administrator=True)
async def gen(ctx, amount: int = 1):
    keys = []
    for _ in range(amount):
        key = f"{secrets.token_hex(4).upper()}-{secrets.token_hex(4).upper()}-{secrets.token_hex(4).upper()}"
        c.execute("INSERT INTO keys (key, used, created_at) VALUES (?, ?, ?)", (key, False, datetime.now().isoformat()))
        keys.append(key)
    conn.commit()
    await ctx.send(f"✅ Generated {amount} key(s):\n```\n" + "\n".join(keys) + "\n```")

@bot.command()
@commands.has_permissions(administrator=True)
async def adduser(ctx, discord_id: str, key: str):
    """Manually add a user (Admin)"""
    c.execute("INSERT OR REPLACE INTO users (discord_id, key, redeem_count, created_at) VALUES (?, ?, ?, ?)",
              (discord_id, key, 1, datetime.now().isoformat()))
    conn.commit()
    await ctx.send(f"✅ Added user {discord_id} with key {key}")

bot.run(os.environ.get("DISCORD_TOKEN"))
