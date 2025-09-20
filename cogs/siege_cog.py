import discord
from discord.ext import commands
from discord import app_commands
import json
import os
from datetime import datetime, time
import pytz
import asyncio

TZ_EU = pytz.timezone("Europe/Berlin")

CONFIG_DIR = "config"
PARTICIPANTS_FILE = os.path.join(CONFIG_DIR, "participants.json")
ARCHIVE_FILE = os.path.join(CONFIG_DIR, "archive.json")

def load_json(path):
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

participants = load_json(PARTICIPANTS_FILE)
archive = load_json(ARCHIVE_FILE)

# ================== Константи винагород ==================
REWARDS = {
    "Balenos": {"goldbar": 4, "medal": 30, "extra": None},
    "Serendia": {"goldbar": 4, "medal": 30, "extra": None},
    "Mediah": {"goldbar": 5, "medal": 45, "extra": None},
    "Valencia": {"goldbar": 5, "medal": 45, "extra": None},
    "Calpheon": {"goldbar": 6, "medal": 60, "extra": "Trace of Thunderbolt ×1"},
    "Kamasylvia": {"goldbar": 6, "medal": 60, "extra": "Trace of Thunderbolt ×1"},
}

# ================== Ліміти по статах ==================
STAT_LIMITS = {
    "Balenos": "AP ≤ 395, DP ≤ 311, ACC ≤ 715, EVA ≤ 750, HP ≤ 6500, Resist ≤ 30%",
    "Serendia": "AP ≤ 395, DP ≤ 311, ACC ≤ 715, EVA ≤ 750, HP ≤ 6500, Resist ≤ 30%",
    "Mediah": "AP ≤ 680, DP ≤ 500, ACC ≤ 920, EVA ≤ 908, HP ≤ 11000",
    "Valencia": "AP ≤ 680, DP ≤ 500, ACC ≤ 920, EVA ≤ 908, HP ≤ 11000",
    "Calpheon": "Без обмежень",
    "Kamasylvia": "Без обмежень",
}

# ================== Побудова таблиці ==================
def build_table(msg_id: str):
    if msg_id not in participants:
        return "Немає учасників."

    data = participants[msg_id]["data"]
    roles = {"Def": [], "SF": [], "Shai": [], "Main": []}

    for uid, info in data.items():
        role = info["role"]
        name = info["name"]
        ts = info["timestamp"]

        # Найм -> тільки емодзі, без окремого блоку
        if role == "Найм":
            name = f"🔹 {name}"
            role = "Main"

        if role in roles:
            roles[role].append((name, ts))

    result = ""
    for role, members in roles.items():
        if not members:
            continue
        result += f"**{role.upper()}**\n"
        result += "```\n"
        result += "№  | Нік                 | Час\n"
        for i, (name, ts) in enumerate(members, start=1):
            result += f"{i:<2} | {name:<18} | <t:{ts}:t>\n"
        result += "```\n\n"

    return result if result else "Немає зареєстрованих учасників."


class SiegeCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ================== Створення облоги ==================
    @app_commands.command(name="siege_create", description="Створити облогу")
    @app_commands.guild_only()
    async def siege_create(
        self,
        interaction: discord.Interaction,
        дата: str,
        територія: str,
        тип: str,       # "Occupation" чи інше
        tier: str,      # T1 / T2 / T3 / T4
        нод: str = "-", # Якщо Occupation → ігноруємо
        слоти: int = 50,
    ):
        await interaction.response.defer(ephemeral=True)

        try:
            siege_date = datetime.strptime(дата, "%d.%m.%Y").date()
        except ValueError:
            return await interaction.followup.send(
                "❌ Невірний формат дати. Використовуй ДД.ММ.РРРР", ephemeral=True
            )

        siege_time_eu = TZ_EU.localize(datetime.combine(siege_date, time(19, 0)))
        unix_time = int(siege_time_eu.timestamp())

        rewards = REWARDS.get(територія, None)
        reward_text = ""
        if rewards:
            reward_text += f"<:tres:1416059303273431163> Винагороди\n"
            reward_text += f"<:goldbar:1416059264602083398> Gold Bar ×{rewards['goldbar']}\n"
            reward_text += f"<:medal:1416059244523819028> Medal of Honor ×{rewards['medal']}\n"
            if rewards["extra"] and tier not in ["T1", "T2"]:
                reward_text += f"✨ {rewards['extra']}\n"

        stats_text = STAT_LIMITS.get(територія, "")
        status_text = "```ansi\n[2;32m АКТИВНЕ [0m\n```"
        table_text = build_table("temp")

        # Якщо Occupation → не пишемо Node
        node_text = f" | Node: {нод}" if тип.lower() != "occupation" else ""

        embed = discord.Embed(
            title=f"⚔️ Облога — Альянс «Дикі Кабани» | {територія} {тип}{node_text}",
            description=(
                f"👥 Учасники: 0/{слоти}\n\n"
                f"📅 Дата: {дата}\n"
                f"🕗 Початок: <t:{unix_time}:F>\n"
                f"🏷️ Тип: {tier}\n"
                f"📊 Статус: {status_text}\n\n"
                f"📌 Обмеження: {stats_text}\n\n"
                f"{table_text}\n"
                f"{reward_text}"
            ),
            color=discord.Color.green(),
        )

        embed.set_thumbnail(url="https://i.imgur.com/SbmQSY0.png")
        embed.set_footer(text="Silent Concierge by Myxa")
        embed.set_image(url="https://i.imgur.com/DoCgmY7.jpeg")

        view = SiegeView(слоти, територія, тип, tier, нод)
        msg = await interaction.channel.send(embed=embed, view=view)

        participants[str(msg.id)] = {"slots": слоти, "data": {}}
        save_json(PARTICIPANTS_FILE, participants)

        asyncio.create_task(self.remind_users(msg.id, unix_time))
        await interaction.followup.send("✅ Облога створена!", ephemeral=True)

    # ================== Архів ==================
    @app_commands.command(name="siege_archive", description="Показати архів облог")
    @app_commands.guild_only()
    async def siege_archive(self, interaction: discord.Interaction):
        if not archive:
            return await interaction.response.send_message("📭 Архів порожній.", ephemeral=True)

        embed = discord.Embed(
            title="📜 Архів облог",
            description="Список завершених облог",
            color=discord.Color.dark_gold(),
        )

        for key, data in archive.items():
            embed.add_field(
                name=f"{data['date']} — {data['territory']} {data['type']} | Node: {data['node']}",
                value=f"👥 {len(data['participants'])}/{data['slots']} | Результат: {data.get('result','-')}",
                inline=False,
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ================== Статистика ==================
    @app_commands.command(name="siege_stats", description="Статистика по учасниках")
    @app_commands.guild_only()
    async def siege_stats(self, interaction: discord.Interaction, період: str = "all"):
        stats = {}
        for _, data in archive.items():
            date = data["date"]
            if період != "all" and період not in date:
                continue
            for uid, info in data["participants"].items():
                name = info["name"]
                role = info["role"]
                stats.setdefault(
                    name, {"Shai": 0, "Def": 0, "SF": 0, "Main": 0, "Найм": 0, "dates": []}
                )
                stats[name][role] += 1
                stats[name]["dates"].append(date)

        if not stats:
            return await interaction.response.send_message("📊 Статистика порожня.", ephemeral=True)

        embed = discord.Embed(
            title="📊 Статистика облог",
            description=f"Період: {період}",
            color=discord.Color.blue(),
        )

        for name, info in stats.items():
            total = sum([info[r] for r in ["Shai", "Def", "SF", "Main", "Найм"]])
            embed.add_field(
                name=name,
                value=(f"Shai: {info['Shai']} | Def: {info['Def']} | SF: {info['SF']} "
                       f"| Main: {info['Main']} | Найм: {info['Найм']}\n"
                       f"Загалом: {total}\n"
                       f"Дати: {', '.join(info['dates'])}"),
                inline=False,
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def remind_users(self, msg_id, start_ts):
        delay = start_ts - int(datetime.now().timestamp()) - 1800
        if delay > 0:
            await asyncio.sleep(delay)
        msg_data = participants.get(str(msg_id), {}).get("data", {})
        for uid in msg_data:
            try:
                user = await self.bot.fetch_user(int(uid))
                await user.send("⚔️ Нагадування! Через 30 хвилин почнеться облога.")
            except Exception:
                pass


# ================== Кнопки ==================
class SiegeView(discord.ui.View):
    def __init__(self, slots, territory, type_, tier, node):
        super().__init__(timeout=None)
        self.slots = slots
        self.territory = territory
        self.type_ = type_
        self.tier = tier
        self.node = node

    @discord.ui.button(label="Shai", style=discord.ButtonStyle.primary)
    async def shai_button(self, interaction, button): await self.add_participant(interaction, "Shai")

    @discord.ui.button(label="Def", style=discord.ButtonStyle.primary)
    async def def_button(self, interaction, button):
        msg_id = str(interaction.message.id)
        if msg_id in participants and sum(1 for p in participants[msg_id]["data"].values() if p["role"] == "Def") >= 5:
            return await interaction.response.send_message("❌ Ліміт Def (5/5).", ephemeral=True)
        await self.add_participant(interaction, "Def")

    @discord.ui.button(label="SF", style=discord.ButtonStyle.primary)
    async def sf_button(self, interaction, button): await self.add_participant(interaction, "SF")

    @discord.ui.button(label="Main", style=discord.ButtonStyle.primary)
    async def main_button(self, interaction, button): await self.add_participant(interaction, "Main")

    @discord.ui.button(label="Найм", style=discord.ButtonStyle.success)
    async def recruit_button(self, interaction, button):
        msg_id = str(interaction.message.id)
        if msg_id in participants and sum(1 for p in participants[msg_id]["data"].values() if p["role"] == "Найм") >= 3:
            return await interaction.response.send_message("❌ Ліміт найму (3/3).", ephemeral=True)
        await self.add_participant(interaction, "Найм")

    @discord.ui.button(label="Відмовитись", style=discord.ButtonStyle.danger)
    async def leave_button(self, interaction, button):
        msg_id = str(interaction.message.id)
        if msg_id in participants and str(interaction.user.id) in participants[msg_id]["data"]:
            del participants[msg_id]["data"][str(interaction.user.id)]
            save_json(PARTICIPANTS_FILE, participants)
            await interaction.response.send_message("🚪 Ти відмовився.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Ти не був зареєстрований.", ephemeral=True)

    @discord.ui.button(label="✅ Перемога", style=discord.ButtonStyle.success)
    async def win_button(self, interaction, button): await self.finish(interaction, "Перемога")

    @discord.ui.button(label="🏰 Взяли Нод", style=discord.ButtonStyle.primary)
    async def node_button(self, interaction, button): await self.finish(interaction, "Взяли Нод")

    @discord.ui.button(label="❌ Програш", style=discord.ButtonStyle.danger)
    async def lose_button(self, interaction, button): await self.finish(interaction, "Програш")

    async def add_participant(self, interaction, role: str):
        msg_id = str(interaction.message.id)
        user_id = str(interaction.user.id)
        if msg_id not in participants:
            participants[msg_id] = {"slots": self.slots, "data": {}}
        participants[msg_id]["data"][user_id] = {
            "name": interaction.user.display_name,
            "role": role,
            "timestamp": int(datetime.now().timestamp()),
        }
        save_json(PARTICIPANTS_FILE, participants)
        await interaction.response.send_message(f"✅ Тебе додано як {role}", ephemeral=True)

    async def finish(self, interaction, result: str):
        msg_id = str(interaction.message.id)
        if msg_id not in participants:
            return await interaction.response.send_message("❌ Немає даних по цій облогі.", ephemeral=True)

        archive[msg_id] = {
            "date": datetime.now().strftime("%d.%m.%Y"),
            "territory": self.territory,
            "type": self.type_,
            "node": self.node if self.type_.lower() != "occupation" else "-",
            "slots": participants[msg_id]["slots"],
            "participants": participants[msg_id]["data"],
            "result": result,
        }
        save_json(ARCHIVE_FILE, archive)

        await interaction.response.send_message(f"🏆 Результат збережено: {result}", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(SiegeCog(bot))
