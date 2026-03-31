import os
import asyncio
import traceback
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List, Tuple

from astral import moon

import discord
from discord.ext import tasks, commands
from discord import app_commands

from utility import _parse_time, _next_run

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("moon")

# ---- Constants & styling helpers ----
DEFAULT_TZ_NAME = "America/Chicago"
HTTP_HEADERS = {
    "User-Agent": "UtilaBot/1.0 (+https://github.com/ethanocurtis/Utilabot)",
    "Accept": "application/json",
}

# ---- Moon phase helpers (Astral) ----
# Astral's moon.phase() returns a number on ~0..28 scale for the given date.
# We'll map that to 8 familiar phases for display.
_MOON_PHASES_8 = [
    ("New Moon", "🌑"),
    ("Waxing Crescent", "🌒"),
    ("First Quarter", "🌓"),
    ("Waxing Gibbous", "🌔"),
    ("Full Moon", "🌕"),
    ("Waning Gibbous", "🌖"),
    ("Last Quarter", "🌗"),
    ("Waning Crescent", "🌘"),
]

def moon_phase_info_for_date(d: datetime) -> Tuple[str, str, float]:
    """Return (name, emoji, age_days) for the date."""
    # Use local date component
    date = d.date()
    p = float(moon.phase(date))  # 0..~28
    idx = int((p / 28.0) * 8 + 0.5) % 8
    name, emoji = _MOON_PHASES_8[idx]
    age_days = round(p, 1)
    return name, emoji, age_days

def _get_moon_embed(date, includePast: bool = False, includeFuture: bool = False):
    name, emoji, age = moon_phase_info_for_date(date)

    emb = discord.Embed(
        title=f"Today's moon is a {emoji} {name}!",
        colour = discord.Colour.greyple()
    )

    emb.add_field(name="This moon is", value=f"{age} days old.", inline=True)

    name, emoji, age = moon_phase_info_for_date(date - timedelta(days=1))
    emb.add_field(name="The previous moon was a", value=f"{emoji} {name}.", inline=True)

    name, emoji, age = moon_phase_info_for_date(date + timedelta(days=1))
    emb.add_field(name="And the following moon will be a", value=f"{emoji} {name}.", inline=True)

    return emb

CADENCE_CHOICES = [
    app_commands.Choice(name="daily", value="daily"),
    app_commands.Choice(name="weekly (send on this weekday)", value="weekly"),
]

class Moon(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        # Try to discover the Store from bot or import-time fallback
        self.store = getattr(bot, "store", None)
        
        if self.store is None:
            log.error("Storage backend not available.")

        self.moon_scheduler.start()

    def cog_unload(self):
        self.moon_scheduler.cancel()

    # -------- Slash Commands --------

    @app_commands.command(name = "moon", description = "Show the current moon phase.")
    async def moon(self, inter: discord.Interaction):
        await inter.response.defer()
        await inter.followup.send(embed = _get_moon_embed(datetime.utcnow(), True, True))

    @app_commands.command(name = "moon_subscribe", description = "Subscribe this channel to a daily or weekly moon phase announcement at a UTC time.")
    @app_commands.describe(
        time = "HH:MM (24h), HHMM, or h:mma/pm in UTC timezone",
        cadence = "daily or weekly",
        weekly_days = "For weekly: number of days to include (3, 7, or 10)"
    )
    @app_commands.choices(cadence = CADENCE_CHOICES)
    @commands.has_permissions(administrator = True)
    async def moon_subscribe(
        self,
        inter: discord.Interaction,
        time: str,
        cadence: app_commands.Choice[str],
        weekly_days: Optional[app_commands.Range[int, 3, 10]] = 7
    ):
        if self.store is None:
            return await inter.response.send_message("Storage backend not available.", ephemeral = True)
        
        await inter.response.defer(ephemeral = True)

        try:
            hh, mi = _parse_time(time)
            now = datetime.utcnow()
            first = _next_run(now, hh, mi, cadence.value)

            sub = {
                "channel_id": inter.channel_id,
                "cadence": cadence.value,
                "hh": int(hh),
                "mi": int(mi),
                "weekly_days": int(weekly_days or 7),
                "next_run": first.isoformat(),
            }

            sid = self.store.add_moon_sub(sub)

            await inter.followup.send(
                f":white_check_mark: Subscribed <#{sub['channel_id']}> to {cadence.value} moon phase announcements at **{first.strftime('%I:%M %p')}**.\n"
                + ("Weekly length: **{} days**.".format(sub['weekly_days']) if cadence.value == "weekly" else "Daily: Today & Tomorrow.") + "\n"
                + f"Subscription #{sid}.",
                ephemeral = True
            )
        except Exception as e:
            await inter.followup.send(f"\u26A0\ufe0f {type(e).__name__}: {e} {traceback.format_exc()}", ephemeral = True)

    @app_commands.command(name="moon_unsubscribe", description="Unsubscribe from moon phase announcements for the current channel.")
    @commands.has_permissions(administrator = True)
    async def moon_unsubscribe(self, inter: discord.Interaction, subscription_id: int):
        if self.store is None:
            return await inter.response.send_message("Storage backend not available.", ephemeral = True)

        await inter.response.defer(ephemeral = True)

        ok = self.store.remove_moon_sub(subscription_id, requester_id=inter.channel_id)

        await inter.followup.send(f":white_check_mark: Moon phase announcement subscription #{subscription_id} in <#{inter.channel_id}> cancelled." if ok else f"Failed to cancel subscription #{subscription_id} in <#{inter.channel_id}>.", ephemeral = True)

    @app_commands.command(name="moon_subscriptions", description="List your moon phase announcement subscriptions and next send time.")
    @commands.has_permissions(administrator = True)
    async def moon_subscriptions(self, inter: discord.Interaction):
        if self.store is None:
            return await inter.response.send_message("Storage backend not available.", ephemeral = True)

        await inter.response.defer(ephemeral = True)

        items = self.store.list_moon_subs(inter.channel_id)

        if not items:
            return await inter.followup.send("There are no moon subscriptions.", ephemeral = True)

        out_lines = []

        for s in items:
            now = datetime.utcnow()
            hh = int(s.get("hh", 8))
            mi = int(s.get("mi", 0))
            cadence = s.get("cadence", "daily") if s.get("cadence") in {"daily", "weekly"} else "daily"

            raw = s.get("next_run")
            nxt = None
            needs = False
            if not raw or str(raw).strip().lower() == "none":
                needs = True
            else:
                try:
                    nxt = datetime.fromisoformat(str(raw))
                except Exception:
                    needs = True

            if not needs and nxt is not None and nxt <= datetime.utcnow():
                needs = True

            if needs:
                first = _next_run(now, hh, mi, cadence)
                nxt = first
                self.store.update_moon_sub(s["id"], channel_id=int(s["channel_id"]), next_run=nxt.isoformat())

            out_lines.append(
                f"#{s['id']} in <#{s['channel_id']}> {cadence} at {hh:02d}:{mi:02d} - next: {nxt.strftime('%m-%d-%Y %H:%M %Z')}"
            )

        await inter.followup.send("\n".join(out_lines), ephemeral=True)

    # -------- Schedulers --------
    @tasks.loop(seconds=60)
    async def moon_scheduler(self):
        if self.store is None:
            return
        
        try:
            now = datetime.utcnow()
            subs = self.store.list_moon_subs(None)

            if not subs:
                return

            for s in subs:
                due = datetime.fromisoformat(s["next_run"])

                if due <= now:
                    try:
                        embs = []

                        if s["cadence"] == "daily":
                            interval = 1
                            noun = "today"

                            embs.append(_get_moon_embed(now))
                        else:
                            days = int(s.get("weekly_days", 7))
                            interval = 10 if days > 10 else (3 if days < 3 else days)
                            noun = "this week"

                            for x in range(0, interval):
                                embs.append(_get_moon_embed(now + timedelta(days = x)))

                        channel = await self.bot.fetch_channel(s["channel_id"])
                        await channel.send(embeds = embs)

                        next = datetime.utcnow()
                        next = next.replace(hour = s["hh"], minute = s["mi"], second = 0, microsecond = 0)

                        if next <= datetime.utcnow():
                            next += timedelta(days = interval)

                        self.store.update_moon_sub(s["id"], channel_id = int(s["channel_id"]), next_run = next.isoformat())
                    except Exception as e:
                        fallback = now + timedelta(minutes = 5)
                        self.store.update_moon_sub(s["id"], next_run = fallback.isoformat())
                        await self.bot.get_channel(s["channel_id"]).send(f"\u26A0\ufe0f Moon error: {e} {traceback.format_exc()}")

        except Exception as e:
            await self.bot.get_channel(1468253598646534294).send(f"\u26A0\ufe0f Moon subscriptions error: {e} {traceback.format_exc()}")

    @moon_scheduler.before_loop
    async def before_moon(self):
        await self.bot.wait_until_ready()

async def setup(bot: commands.Bot):
    await bot.add_cog(Moon(bot))