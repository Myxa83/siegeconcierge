import discord
from discord.ext import commands, tasks
import os
import asyncio
import json
from dotenv import load_dotenv
from datetime import datetime
import pytz

# ===== Завантаження .env =====
CONFIG_DIR = "config"
os.makedirs(CONFIG_DIR, exist_ok=True)

load_dotenv(os.path.join(CONFIG_DIR, ".env.siege"))

TOKEN = os.getenv("DISCORD_TOKEN_SIEGE")
SIEGE_GUILD_ID = int(os.getenv("SIEGE_GUILD_ID", "0"))

if not TOKEN or not SIEGE_GUILD_ID:
    raise ValueError("❌ Перевір DISCORD_TOKEN_SIEGE і SIEGE_GUILD_ID у .env.siege")

# ===== Статуси з JSON =====
STATUS_FILE = os.path.join(CONFIG_DIR, "status_phrases.json")

def load_statuses():
    try:
        with open(STATUS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError
            return data
    except Exception:
        return {
            "day": ["Грає у облогу", "Грає у підготовку до війни"],
            "night": ["Грає у нічний рейд", "Грає у темні битви"]
        }

status_phrases = load_statuses()

# ===== Інтенти =====
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ===== Цикл статусів =====
@tasks.loop(minutes=5)
async def change_status():
    tz = pytz.timezone("Europe/London")
    hour = datetime.now(tz).hour
    mode = "day" if 8 <= hour < 23 else "night"

    phrases = status_phrases.get(mode, [])
    if not phrases:
        phrases = ["Грає у Silent Siege"]

    phrase = phrases[datetime.now().second % len(phrases)]
    await bot.change_presence(activity=discord.Game(name=phrase))

# ===== Події =====
@bot.event
async def on_ready():
    print(f"✅ Увійшов як {bot.user} (ID: {bot.user.id})")
    try:
        guild = discord.Object(id=SIEGE_GUILD_ID)
        synced = await bot.tree.sync(guild=guild)  # локальна синхра тільки для цього сервера
        print(f"🌐 Синхронізовано {len(synced)} команд для гільдії {SIEGE_GUILD_ID}")
    except Exception as e:
        print(f"⚠️ Помилка синхронізації: {e}")

    change_status.start()  # запускаємо статуси

# ===== Завантаження когів =====
async def load_cogs():
    try:
        await bot.load_extension("cogs.siege_cog")
        print("⚔️ Cog siege_cog завантажено")
    except Exception as e:
        print(f"❌ Не вдалося завантажити siege_cog: {e}")

async def main():
    async with bot:
        await load_cogs()
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())