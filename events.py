import os
import re
import html
import json
import aiohttp
import asyncio
import traceback
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List, Tuple

import discord
from discord.ext import tasks, commands
from discord import app_commands

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("events")

# ---- Constants & styling helpers ----
DEFAULT_TZ_NAME = "America/Chicago"
HTTP_HEADERS = {
    "User-Agent": "UtilaBot/1.0 (+https://github.com/ethanocurtis/Utilabot)",
    "Accept": "application/json",
}

class Events(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        # Try to discover the Store from bot or import-time fallback
        self.store = getattr(bot, "store", None)
        
        if self.store is None:
            log.error("Storage backend not available.")

        self.events_scheduler.start()

    def cog_unload(self):
        self.events_scheduler.cancel()

    def processEventList(self, cadence, events, channel):
        if cadence == "daily":
            interval = 1
            noun = "today"
        else:
            interval = 7
            noun = "this week"

        if (len(events) > 1)
            emb = discord.Embed(
                title=f"\U0001F324\ufe0f {len(events) Events happening {noun}!",
                colour="1e90ff"
            )

            for (event in events)
                # if event is more than interval away, ignore it
                emb.add_field(name="Name", value=event.name, inline=False)

                if (description in event)
                    emb.add_field(name="Description", value=event.description, inline=False)

                if (start_time in event)
                    emb.add_field(name="When", value=event.start_time, inline=False)

                if (location in event)
                    emb.add_field(name="Where", value=event.location, inline=False)

                if (user_count in event)
                    emb.add_field(name="Interested", value=event.user_count, inline=False)

            #emb.set_footer(text=f"Scheduled in {tz_name} • Units: {units}")

            #days = int(s.get("weekly_days", 7))
            #days = 10 if days > 10 else (3 if days < 3 else days)
        else:
            emb = discord.Embed(
                title=f"There are no events happening {noun}... :sadblob:",
                colour="1e90ff"
            )

        await channel.send(embed = emb)

    # -------- Slash Commands --------

    @app_commands.command(name="events_subscribe", description="Subscribe this channel to a daily or weekly event announcement at a UTC time.")
    @app_commands.describe(
        time="HH:MM (24h), HHMM, or h:mma/pm in YOUR saved timezone",
        cadence="daily or weekly",
        weekly_days="For weekly: number of days to include (3, 7, or 10)"
    )
    @app_commands.choices(cadence=CADENCE_CHOICES)
    async def events_subscribe(
        self,
        inter: discord.Interaction,
        time: str,
        cadence: app_commands.Choice[str],
        weekly_days: Optional[app_commands.Range[int, 3, 10]] = 7
    ):
        if self.store is None:
            return await inter.response.send_message("Storage backend not available.", ephemeral=True)
        await inter.response.defer(ephemeral=True)
        try:
            hh, mi = _parse_time(time)
            now = datetime.now()
            first = _next_local_run(now, hh, mi, cadence.value)

            sub = {
                "channel_id": inter.channel_id,
                "cadence": cadence.value,
                "hh": int(hh),
                "mi": int(mi),
                "weekly_days": int(weekly_days or 7),
                "next_run_utc": next_run_utc.isoformat(),
            }

            self.store.add_events_sub(sub)

            await inter.followup.send(
                f"\U0001F324\ufe0f Subscribed <@{sub['channel_id']}> to {cadence.value} event announcements at **{first_local.strftime('%I:%M %p')}**.\n"
                + ("Weekly length: **{} days**.".format(sub['weekly_days']) if cadence.value == "weekly" else "Daily: Today & Tomorrow.")
                ephemeral=True
            )
        except Exception as e:
            await inter.followup.send(f"\u26A0\ufe0f {type(e).__name__}: {e} {traceback.format_exc()}", ephemeral=True)

    @app_commands.command(name="events_subscriptions", description="List your event announcement subscriptions and next send time.")
    async def events_subscriptions(self, inter: discord.Interaction):
        if self.store is None:
            return await inter.response.send_message("Storage backend not available.", ephemeral=True)

        await inter.response.defer(ephemeral=True)
        items = self.store.list_weather_subs(inter.channel_id)
        if not items:
            return await inter.followup.send("You have no events subscriptions.", ephemeral=True)

        out_lines = []

        for s in items:
            now = datetime.now()
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
                    nxt = datetime.fromisoformat(str(raw)).replace(tzinfo=timezone.utc)
                except Exception:
                    needs = True

            if not needs and nxt is not None and nxt <= datetime.now(timezone.utc):
                needs = True

            if needs:
                first = _next_local_run(now, hh, mi, cadence)
                nxt = first
                self.store.update_event_sub(s["id"], channel_id=int(s["channel_id"]), next_run=nxt.isoformat())

            out_lines.append(
                f"<@{s['channel_id']}> — {cadence} at {hh:02d}:{mi:02d} - next: {_fmt_local(nxt)}"
            )

        await inter.followup.send("\n".join(out_lines), ephemeral=True)

    @app_commands.command(name="events_list", description="Show the list of upcoming events.")
    async def events_unsubscribe(self, inter: discord.Interaction, sub_id: int):
        processEventList(s, events)

    # -------- Schedulers --------
    @tasks.loop(seconds=60)
    async def events_scheduler(self):
        if self.store is None:
            return
		
        try:
            now = datetime.now()
            subs = self.store.list_event_subs(None)

            if not subs:
                return

            for s in subs:
                due = datetime.fromisoformat(s["next_run"])

                if due <= now:
                    try:
                        channel = await self.bot.fetch_channel(int(s["channel_id"]))
                        events = channel.guild.scheduled_events

                        processEventList(s["cadence"], events, channel)

                        next = datetime.now()
                        next = next.replace(hour=s["hh"], minute=s["mi"], second=0, microsecond=0)

                        if next <= datetime.now():
                            next += timedelta(days=interval)

                        self.store.update_event_sub(s["id"], channel_id=int(s["channel_id"]), next_run=next.isoformat())
                    except Exception as e:
                        fallback = now_utc + timedelta(minutes=5)
                        self.store.update_event_sub(s["id"], next_run=fallback.isoformat())
                        await self.bot.get_channel(s["channel_id"]).send(f"\u26A0\ufe0f Events error: {e} {traceback.format_exc()}")

        except Exception as e:
            await self.bot.get_channel(1468253598646534294).send(f"\u26A0\ufe0f Events subscription error: {e} {traceback.format_exc()}")

    @events_scheduler.before_loop
    async def before_events(self):
        await self.bot.wait_until_ready()

async def setup(bot: commands.Bot):
    await bot.add_cog(Events(bot))