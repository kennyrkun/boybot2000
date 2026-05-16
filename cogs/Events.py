import os
import asyncio
import traceback
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List, Tuple

import discord
from discord.ext import tasks, commands
from discord import app_commands

from utility import _parse_time, _next_run

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

class Events(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        self.events_scheduler.start()

    group = app_commands.Group(name = "events", description = "Event commands.")

    def cog_unload(self):
        self.events_scheduler.cancel()

    def check_cog_enabled(self, guildId: int):
        return type(self).__name__ in self.bot.store.get_enabled_extensions(guildId)

    def cog_check(self, ctx):
        return self.check_cog_enabled(ctx.guild.id)

    def interaction_check(self, inter):
        return self.check_cog_enabled(inter.guild.id)

    # -------- Helper functions ---------

    # have to keep channel ID in this because even though it doesn't send, NaturalLanguage needs to know the guildId
    async def _get_event_list(self, channelId: int, interval: int, noun: str, now: datetime):
        channel = await self.bot.fetch_channel(channelId)
        events = channel.guild.scheduled_events

        eventsInInterval = []
        eventsInFuture   = []
        earliestEvent    = None

        ignorePastDate = now + timedelta(days = interval)
        ignorePastDate2 = now + timedelta(days = 14)

        for event in events:
            if event.status is not discord.EventStatus.scheduled and event.status is not discord.EventStatus.active:
                continue

            if earliestEvent is None or event.start_time < earliestEvent.start_time:
                earliestEvent = event

            if event.start_time.timestamp() > ignorePastDate.timestamp():
                # don't show events waaaaaay in the future at all
                if event.start_time.timestamp() > ignorePastDate2.timestamp():
                    continue

                eventsInFuture.append(event)
                continue

            eventsInInterval.append(event)

        eventsInInterval.sort(key = lambda x: x.start_time, reverse = False)
        eventsInFuture.sort(key = lambda x: x.start_time, reverse = False)

        # add in-interval events first so that they are shown first in embeds
        allEvents = eventsInInterval + eventsInFuture

        if len(allEvents) > 0:
            currentEventsCount = len(eventsInInterval)
            futureEventCount = len(eventsInFuture)

            strings = []

            if currentEventsCount > 0:
                strings.append(f"there {'are' if (currentEventsCount > 1) else 'is'} {currentEventsCount} event{'s' if currentEventsCount > 1 else ''} {noun}")

            if futureEventCount > 0:
                strings.append(f"there {'are' if futureEventCount > 1 else 'is'} {futureEventCount} event{'s' if futureEventCount > 1 else ''} in the near future")

            string = " and ".join(strings).capitalize() + "!\n"

            urls = ""
            prompt = ""

            for event in allEvents:
                urls += f"[{event.name}]({event.url})\n"
                prompt += f"Name: {event.name}\nDescription: {event.description}\nStart time: {event.start_time} URL: {event.url}"

            response = (
                await self.bot.NaturalLanguage.prompt(channel.guild.id, "Given the list of events provided, generate a small list of upcoming events ordered by date and include a short description. Format the name of each event like this: [Name](URL). Here is the list of events:" + prompt) 
                or 
                string + urls
            )

            return response
        else:
            return f"There are no events {noun} or in the near future... :boykisser_sob:"

    # -------- Discord ScheduledEvent events -------

    @commands.Cog.listener()
    async def on_scheduled_event_create(self, event: discord.ScheduledEvent):
        # TODO: add cog check for guild here
        
        now = datetime.utcnow()
        subs = self.bot.store.list_event_subs(None)

        if not subs:
            return

        sent_channels = []

        for s in subs:
            if s["guild_id"] == event.guild.id:
                if s["channel_id"] not in sent_channels:
                    channel = await self.bot.fetch_channel(int(s["channel_id"]))
                    await channel.send(content = f"[new event just dropped uwu :333]({event.url})")

    @commands.Cog.listener()
    async def on_scheduled_event_delete(self, event: discord.ScheduledEvent):
        # TODO: add cog check for guild here
        
        now = datetime.utcnow()
        subs = self.bot.store.list_event_subs(None)

        if not subs:
            return

        sent_channels = []

        for s in subs:
            if s["guild_id"] == event.guild.id:
                if s["channel_id"] not in sent_channels:
                    channel = await self.bot.fetch_channel(int(s["channel_id"]))
                    await channel.send(content = f"The event `{event.name}` was deleted. :boykisser_pensive:")
                    sent_channels.append(s["channel_id"])

    @commands.Cog.listener()
    async def on_scheduled_event_update(self, before: discord.ScheduledEvent, after: discord.ScheduledEvent):
        # TODO: add cog check for guild here
        
        now = datetime.utcnow()
        subs = self.bot.store.list_event_subs(None)

        if not subs:
            return

        sent_channels = []

        for s in subs:
            if s["guild_id"] == after.guild.id:
                if s["channel_id"] not in sent_channels:
                    sent_channels.append(s["channel_id"])
                    channel = await self.bot.fetch_channel(int(s["channel_id"]))

                    if before.status != after.status:
                        if after.status == discord.EventStatus.active:
                            channel.send(content = f"`{after.name}` has begun!")
                        elif after.status == discord.EventStatus.completed:
                            channel.send(content = f"`{after.name}` is now over.")
                        elif after.status == discord.EventStatus.cancelled:
                            channel.send(content = f"`{after.name}` has been cancelled! :boykisser_damn:")

                        return

                    changes = []

                    if before.name != after.name:
                        changes.append(f"**Name**: `{before.name}` => `{after.name}`.")

                    if before.description != after.description:
                        changes.append(f"**Location**: `{before.description}` => `{after.description}`.")

                    if before.start_time != after.start_time:
                        changes.append(f"**Start time**: <t:{int(before.start_time.timestamp())}:f> => <t:{int(after.start_time.timestamp())}:F>.")

                    if before.end_time != after.end_time:
                        changes.append(f"**End time**: <t:{int(before.end_time.timestamp())}:F> => <t:{int(after.end_time.timestamp())}:F>.")

                    if before.location != after.location:
                        changes.append(f"**Location**: `{before.location}` => `{after.location}`.")

                    string = f"[{after.name}]({after.url}) has been updated!\n"

                    for change in changes:
                        string += change + "\n"

                    await channel.send(content = string)

    # -------- Slash Commands --------

    @group.command(name = "list", description = "Show a list of events in the current channel.")
    async def events_list(self, inter: discord.Interaction):
        await inter.response.defer()
        events = await self._get_event_list(inter.channel_id, 1, "today", datetime.utcnow())
        await inter.followup.send(events)

    @group.command(name = "subscribe", description = "Subscribe this channel to a daily or weekly event announcement at a UTC time.")
    @app_commands.describe(
        time = "HH:MM (24h), HHMM, or h:mma/pm in UTC timezone",
        cadence = "daily or weekly",
        weekly_days = "For weekly: number of days to include (3, 7, or 10)"
    )
    @app_commands.choices(cadence = CADENCE_CHOICES)
    @commands.has_permissions(administrator = True)
    async def events_subscribe(
        self,
        inter: discord.Interaction,
        time: str,
        cadence: app_commands.Choice[str],
        weekly_days: Optional[app_commands.Range[int, 3, 10]] = 7
    ):
        await inter.response.defer(ephemeral = True)

        try:
            hh, mi = _parse_time(time)
            now = datetime.utcnow()
            first = _next_run(now, hh, mi, cadence.value)

            sub = {
                "channel_id": inter.channel_id,
                "guild_id": inter.guild_id,
                "cadence": cadence.value,
                "hh": int(hh),
                "mi": int(mi),
                "weekly_days": int(weekly_days or 7),
                "next_run": first.isoformat(),
            }

            sid = self.bot.store.add_event_sub(sub)

            await inter.followup.send(
                f":white_check_mark: Subscribed <#{sub['channel_id']}> to {cadence.value} event announcements at **{first.strftime('%I:%M %p')}**.\n"
                + ("Weekly length: **{} days**.".format(sub['weekly_days']) if cadence.value == "weekly" else "Daily: Today & Tomorrow.") + "\n"
                + f"Subscription #{sid}.",
                ephemeral=True
            )
        except Exception as e:
            log.error(f"\u26A0\ufe0f {type(e).__name__}: {e}\n{traceback.format_exc()}")
            await inter.followup.send(f"sniffles... i cant do it boss... i cant do it...", ephemeral = True)

    @group.command(name = "unsubscribe", description = "Unsubscribe from event announcements for the current channel.")
    @commands.has_permissions(administrator = True)
    async def events_unsubscribe(self, inter: discord.Interaction, subscription_id: int):
        await inter.response.defer(ephemeral = True)

        ok = self.bot.store.remove_event_sub(subscription_id, requester_id = inter.channel_id)

        await inter.followup.send(f":white_check_mark: Event announcement subscription #{subscription_id} in <#{inter.channel_id}> cancelled." if ok else f"Failed to cancel subscription #{subscription_id} in <#{inter.channel_id}>.", ephemeral=True)

    @group.command(name = "subscriptions", description = "List your event announcement subscriptions and next send time.")
    @commands.has_permissions(administrator = True)
    async def events_subscriptions(self, inter: discord.Interaction):
        await inter.response.defer(ephemeral = True)

        items = self.bot.store.list_event_subs(inter.channel_id)

        if not items:
            return await inter.followup.send("There are no events subscriptions.", ephemeral = True)

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
                self.bot.store.update_event_sub(s["id"], channel_id = int(s["channel_id"]), next_run = nxt.isoformat())

            out_lines.append(
                f"#{s['id']} in <#{s['channel_id']}> {cadence} at {hh:02d}:{mi:02d} - next: {nxt.strftime('%m-%d-%Y %H:%M %Z')}"
            )

        await inter.followup.send("\n".join(out_lines), ephemeral = True)

    # -------- Schedulers --------
    @tasks.loop(seconds = 60)
    async def events_scheduler(self):
        try:
            now = datetime.utcnow()
            subs = self.bot.store.list_event_subs(None)

            if not subs:
                return

            for s in subs:
                if not self.check_cog_enabled(s["guild_id"]):
                    return

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
                        channel = await self.bot.fetch_channel(s["channel_id"])
                        events = await self._get_event_list(channel.id, interval, noun, now)
                        await channel.send(events, delete_after = 86400)

                        next = datetime.utcnow()
                        next = next.replace(hour = s["hh"], minute = s["mi"], second = 0, microsecond = 0)

                        if next <= datetime.utcnow():
                            next += timedelta(days = interval)

                        self.bot.store.update_event_sub(s["id"], channel_id = int(s["channel_id"]), next_run = next.isoformat())
                    except Exception as e:
                        fallback = now + timedelta(minutes = 5)
                        self.bot.store.update_event_sub(s["id"], next_run = fallback.isoformat())
                        log.error(f"Events error: {e}\n{traceback.format_exc()}")

        except Exception as e:
            log.error(f"Events subscription error: {e}\n{traceback.format_exc()}")

    @events_scheduler.before_loop
    async def before_events(self):
        await self.bot.wait_until_ready()

async def setup(bot: commands.Bot):
    await bot.add_cog(Events(bot))
