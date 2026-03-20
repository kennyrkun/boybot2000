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

CADENCE_CHOICES = [
    app_commands.Choice(name="daily", value="daily"),
    app_commands.Choice(name="weekly (send on this weekday)", value="weekly"),
]

def _next_run(now: datetime, hh: int, mi: int, cadence: str) -> datetime:
    target = now.replace(hour=hh, minute=mi, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1 if cadence == "daily" else 7)
    return target

def _parse_time(time_str: str):
    t = time_str.strip().lower().replace(" ", "")
    m = re.match(r"^(\d{1,2}):(\d{2})(am|pm)?$", t) or re.match(r"^(\d{2})(\d{2})(am|pm)?$", t)
    if not m:
        raise ValueError("Time must be HH:MM (24h), HHMM, or h:mma/pm.")
    hh, mi, ampm = m.groups()
    hh, mi = int(hh), int(mi)
    if ampm:
        hh = (hh % 12) + (12 if ampm == "pm" else 0)
    if not (0 <= hh <= 23 and 0 <= mi <= 59):
        raise ValueError("Invalid time.")
    return hh, mi

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

    async def _create_event_embed(self, event: discord.ScheduledEvent):
        if event.creator is None:
            event.creator = await self.bot.fetch_user(event.creator_id)

        emb = discord.Embed(
            title = event.name,
            colour = event.creator.accent_colour
        )

        if event.user_count > 0: 
            emb.add_field(name = "Interested", value = event.user_count, inline=True)

        emb.add_field(name = "When", value = event.start_time, inline=True)
        emb.add_field(name = "Where", value = event.location, inline=True)

        emb.add_field(name = None, value = event.description, inline=False)

        emb.set_author(name = event.creator.display_name, url = None, icon_url = event.creator.avatar.url)

        return emb

    # -------- Slash Commands --------

    @app_commands.command(name="events_subscribe", description="Subscribe this channel to a daily or weekly event announcement at a UTC time.")
    @app_commands.describe(
        time="HH:MM (24h), HHMM, or h:mma/pm in UTC timezone",
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

            sid = self.store.add_event_sub(sub)

            await inter.followup.send(
                f":white_check_mark: Subscribed <#{sub['channel_id']}> to {cadence.value} event announcements at **{first.strftime('%I:%M %p')}**.\n"
                + ("Weekly length: **{} days**.".format(sub['weekly_days']) if cadence.value == "weekly" else "Daily: Today & Tomorrow.") + "\n"
                + f"Subscription #{sid}.",
                ephemeral=True
            )
        except Exception as e:
            await inter.followup.send(f"\u26A0\ufe0f {type(e).__name__}: {e} {traceback.format_exc()}", ephemeral=True)

    @app_commands.command(name="events_unsubscribe", description="Unsubscribe from event announcements for the current channel.")
    async def events_unsubscribe(self, inter: discord.Interaction, subscription_id: int):
        if self.store is None:
            return await inter.response.send_message("Storage backend not available.", ephemeral=True)
        await inter.response.defer(ephemeral=True)
        ok = self.store.remove_event_sub(subscription_id, requester_id=inter.channel_id)
        await inter.followup.send(f":white_check_mark: Event announcement subscription #{subscription_id} in <#{inter.channel_id}> cancelled." if ok else f"Failed to cancel subscription #{subscription_id} in <#{inter.channel_id}>.", ephemeral=True)

    @app_commands.command(name="events_subscriptions", description="List your event announcement subscriptions and next send time.")
    async def events_subscriptions(self, inter: discord.Interaction):
        if self.store is None:
            return await inter.response.send_message("Storage backend not available.", ephemeral=True)

        await inter.response.defer(ephemeral=True)

        items = self.store.list_event_subs(inter.channel_id)

        if not items:
            return await inter.followup.send("There are no events subscriptions.", ephemeral=True)

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
                self.store.update_event_sub(s["id"], channel_id=int(s["channel_id"]), next_run=nxt.isoformat())

            out_lines.append(
                f"#{s['id']} in <#{s['channel_id']}> {cadence} at {hh:02d}:{mi:02d} - next: {nxt.strftime('%m-%d-%Y %H:%M %Z')}"
            )

        await inter.followup.send("\n".join(out_lines), ephemeral=True)

    # -------- Schedulers --------
    @tasks.loop(seconds=60)
    async def events_scheduler(self):
        if self.store is None:
            return
		
        try:
            now = datetime.utcnow()
            subs = self.store.list_event_subs(None)

            if not subs:
                return

            for s in subs:
                if s["cadence"] == "daily":
                    interval = 1
                    noun = "today"
                else:
                    days = int(s.get("weekly_days", 7))
                    interval = 10 if days > 10 else (3 if days < 3 else days)
                    noun = "this week"

                due = datetime.fromisoformat(s["next_run"])

                if due <= now:
                    try:
                        channel = await self.bot.fetch_channel(int(s["channel_id"]))
                        events = channel.guild.scheduled_events

                        eventsInInterval = []
                        eventsInFuture   = []
                        earliestEvent    = None

                        if len(events) > 1:
                            ignorePastDate = now + timedelta(days = interval)

                            for event in events:
                                if earliestEvent is None or event.start_time < earliestEvent.start_time:
                                    earliestEvent = event

                                if event.start_time.timestamp() > ignorePastDate.timestamp():
                                    eventsInFuture.append(event)
                                    continue

                                eventsInInterval.append(event)

                            eventsInInterval.sort(key = lambda x: x.start_time, reverse=True)
                            eventsInFuture.sort(key = lambda x: x.start_time, reverse=True)

                            # add in-interval events first so that they are shown first in embeds
                            allEvents = eventsInInterval + eventsInFuture
                            
                            embeds = []

                            # create an embed for the first 10 events ordered by sooner start_time, max of 10 (discord limitation but also that's enough)
                            for x in range(1, max(len(allEvents), 10)):
                                embed = await self._create_event_embed(allEvents[x])
                                embeds.append(embed)

                            currentEventsCount = len(eventsInInterval)
                            futureEventCount = len(eventsInFuture)

                            strings = []

                            if currentEventsCount > 0:
                                strings.append(f"there {'are' if (currentEventsCount > 1) else 'is'} {currentEventsCount} event{'s' if currentEventsCount > 1 else ''} {noun}")

                            if futureEventCount > 0:
                                strings.append(f"there {'are' if futureEventCount > 1 else 'is'} {futureEventCount} event{'s' if futureEventCount > 1 else ''} in the future")

                            string = " and ".join(strings).capitalize() + "!"

                            await channel.send(content = string, embeds = embeds, delete_after = 86400)
                        else:
                            await channel.send("There are no events {noun} or in the future... :boykisser_sob:")

                        next = datetime.utcnow()
                        next = next.replace(hour=s["hh"], minute=s["mi"], second=0, microsecond=0)

                        if next <= datetime.utcnow():
                            next += timedelta(days=interval)

                        self.store.update_event_sub(s["id"], channel_id=int(s["channel_id"]), next_run=next.isoformat())
                    except Exception as e:
                        fallback = now + timedelta(minutes=5)
                        self.store.update_event_sub(s["id"], next_run=fallback.isoformat())
                        await self.bot.get_channel(s["channel_id"]).send(f"\u26A0\ufe0f Events error: {e} {traceback.format_exc()}")

        except Exception as e:
            await self.bot.get_channel(1468253598646534294).send(f"\u26A0\ufe0f Events subscription error: {e} {traceback.format_exc()}")

    @events_scheduler.before_loop
    async def before_events(self):
        await self.bot.wait_until_ready()

async def setup(bot: commands.Bot):
    await bot.add_cog(Events(bot))