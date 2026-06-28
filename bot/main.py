"""Discord absence bot — the operational front door of the staffing cockpit.

Flow (Workstream B): operative types free text in the absence channel → bot parses it with the LLM
(src/absence_parse) → POSTs to the Helios API (/api/absences) → echoes the coverage impact back to the
channel and the planner sees the day go red in the app.

Identity: a member can `/register name:<x>` to enroll once; otherwise their Discord display name is used.
Requires the MESSAGE CONTENT intent (free-text) and the applications.commands scope (slash commands).

Run:  python -m bot.main   (or scripts/run_bot.sh). Needs DISCORD_BOT_TOKEN + the API on :8000.
"""
from __future__ import annotations

import os

import discord
from discord import app_commands
from discord.ext import commands
import httpx

try:
    from dotenv import load_dotenv, find_dotenv
    load_dotenv(find_dotenv(usecwd=True))
except Exception:
    pass

TOKEN = os.environ["DISCORD_BOT_TOKEN"]
CHANNEL_ID = int(os.environ.get("DISCORD_ABSENCE_CHANNEL_ID", "0"))
GUILD_ID = int(os.environ.get("DISCORD_GUILD_ID", "0"))
API = os.environ.get("HELIOS_API", "http://localhost:8000")

from src.absence_parse import parse_absence  # noqa: E402
from bot import registry  # noqa: E402

intents = discord.Intents.default()
intents.message_content = True  # privileged — enable in the Developer Portal
bot = commands.Bot(command_prefix="!", intents=intents)


def _plan_dates():
    return httpx.get(f"{API}/api/plan/dates", timeout=10).json()


def _window_hint(dates) -> str:
    return f"{dates[0]['date']} ({dates[0]['weekday']}) – {dates[-1]['date']} ({dates[-1]['weekday']})"


@bot.event
async def on_ready():
    # Guild-scoped sync makes the slash command appear instantly (global sync can take ~1h).
    if GUILD_ID:
        guild = discord.Object(id=GUILD_ID)
        bot.tree.copy_global_to(guild=guild)
        await bot.tree.sync(guild=guild)
    print(f"Absence bot online as {bot.user}. Listening on channel {CHANNEL_ID or 'ALL'}.", flush=True)


@bot.tree.command(name="register", description="Enroll yourself so shift absences are logged under your name.")
@app_commands.describe(name="The name to log your absences under (e.g. your full name).")
async def register(interaction: discord.Interaction, name: str):
    registry.register(interaction.user.id, name.strip())
    await interaction.response.send_message(
        f"Registered as **{name.strip()}**. Future absences you report will be logged under this name.",
        ephemeral=True,
    )


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    if CHANNEL_ID and message.channel.id != CHANNEL_ID:
        return

    try:
        dates = _plan_dates()
        parsed = parse_absence(message.content, dates)
    except Exception as e:  # API down / parse failure → stay quiet but log
        print(f"parse error: {e}", flush=True)
        return

    if not parsed.is_absence:
        return  # unrelated chatter — stay silent

    # Absence intent detected. If we couldn't map it to a plannable day, say so instead of going silent.
    if not parsed.date:
        await message.reply(
            "I understood that as an absence, but I couldn't match it to a day in the current plan. "
            f"The plan currently covers **{_window_hint(dates)}** (weekdays). "
            "Try a date in that window, e.g. *“off on Oct 6, sick”*."
        )
        return

    worker = registry.name_for(message.author.id, message.author.display_name)
    try:
        resp = httpx.post(f"{API}/api/absences", timeout=15, json={
            "worker": worker, "date": parsed.date, "reason": parsed.reason, "source": "discord"})
        resp.raise_for_status()
        impact = resp.json()
    except Exception as e:
        await message.reply(f"Couldn't log that absence — the planning service is unreachable. ({e})")
        return

    emoji = "🟥" if impact["sla_breach"] else ("🟨" if impact["short_by"] else "🟩")
    embed = discord.Embed(
        title=f"{emoji} Absence logged — {impact['weekday']} {impact['date']}",
        description=impact["message"],
        color=0xFB6C4A if impact["sla_breach"] else 0xFBB03B if impact["short_by"] else 0x00C04D,
    )
    embed.add_field(name="Worker", value=worker, inline=True)
    embed.add_field(name="Reason", value=parsed.reason or "—", inline=True)
    embed.add_field(name="Coverage",
                    value=f"{impact['confirmed_headcount']}/{impact['target_headcount']}", inline=True)
    embed.add_field(name="Recommendation", value=impact["recommendation"], inline=False)
    await message.reply(embed=embed)


if __name__ == "__main__":
    bot.run(TOKEN)
