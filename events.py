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

    # -------- Slash Commands --------

    @app_commands.command(name="events_subscribe", description="Subscribe this channel to a daily or weekly events announcement at a UTC time.")
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

    @app_commands.command(name="events_subscriptions", description="List your events subscriptions and next send time.")
    async def weather_subscriptions(self, inter: discord.Interaction):
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

    @app_commands.command(name="events_unsubscribe", description="Unsubscribe from events announcements by channel ID.")
    async def weather_unsubscribe(self, inter: discord.Interaction, sub_id: int):
        if self.store is None:
            return await inter.response.send_message("Storage backend not available.", ephemeral=True)

        await inter.response.defer(ephemeral=True)
        ok = self.store.remove_weather_sub(sub_id, requester_id=inter.channel_id)
        await inter.followup.send("Removed." if ok else "Could not remove <@{inter.channel_id}>'s subscription.", ephemeral=True)

    # -------- Schedulers --------
    @tasks.loop(seconds=60)
    async def events_scheduler(self):
        if self.store is None:
            return
        try:
            now_utc = datetime.now(timezone.utc)
            subs = self.store.list_weather_subs(None)
            if not subs:
                return
            async with aiohttp.ClientSession(headers=HTTP_HEADERS) as session:
                for s in subs:
                    due = datetime.fromisoformat(s["next_run_utc"]).replace(tzinfo=timezone.utc)
                    if due <= now_utc:
                        try:
                            user = await self.bot.fetch_channel(int(s["channel_id"]))
                            city, state, lat, lon = await _zip_to_place_and_coords(session, s["zip"])
                            tz_name = (s.get("tz_name") or "").strip() or _get_user_tz_name(self.store, int(s["channel_id"]))
                            units = (s.get("units") or "").strip().lower() or _get_user_units(self.store, int(s["channel_id"]))
                            if s["cadence"] == "daily":
                                outlook = await _fetch_outlook(session, lat, lon, days=2, tz_name=tz_name, units=units)
                                first_hi = outlook[0][5] if outlook and outlook[0][5] is not None else None
                                first_hi_f = None
                                if first_hi is not None:
                                    try:
                                        first_hi_f = float(first_hi) if units == "standard" else (float(first_hi) * 9.0 / 5.0 + 32.0)
                                    except Exception:
                                        first_hi_f = None
                                emb = discord.Embed(
                                    title=f"\U0001F324\ufe0f Daily Outlook — {city}, {state} {s['zip']}",
                                    colour=wx_color_from_temp_f(first_hi_f if first_hi_f is not None else 70)
                                )
                                for (d, line, sunrise, sunset, uv, _hi) in outlook:
                                    extras = []
                                    if sunrise: extras.append(f"\U0001F305 {fmt_sun(sunrise)}")
                                    if sunset: extras.append(f"\U0001F307 {fmt_sun(sunset)}")
                                    if uv is not None: extras.append(f"\U0001F506 UV {round(uv,1)}")
                                    value = "\n".join([line, " - ".join(extras)]) if extras else line
                                    emb.add_field(name=d, value=value, inline=False)
                                emb.set_footer(text=f"Scheduled in {tz_name} • Units: {units}")
                                await user.send(embed=emb)
                                tz = _tzinfo_from_name(tz_name)
                                next_local = datetime.now(tz)
                                next_local = next_local.replace(hour=s["hh"], minute=s["mi"], second=0, microsecond=0)
                                if next_local <= datetime.now(tz):
                                    next_local += timedelta(days=1)
                                self.store.update_weather_sub(s["id"], channel_id=int(s["channel_id"]), next_run_utc=next_local.astimezone(timezone.utc).isoformat())
                            else:
                                days = int(s.get("weekly_days", 7))
                                days = 10 if days > 10 else (3 if days < 3 else days)
                                outlook = await _fetch_outlook(session, lat, lon, days=days, tz_name=tz_name, units=units)
                                first_hi = outlook[0][5] if outlook and outlook[0][5] is not None else None
                                first_hi_f = None
                                if first_hi is not None:
                                    try:
                                        first_hi_f = float(first_hi) if units == "standard" else (float(first_hi) * 9.0 / 5.0 + 32.0)
                                    except Exception:
                                        first_hi_f = None
                                emb = discord.Embed(
                                    title=f"\U0001F5D3\ufe0f Weekly Outlook ({days} days) — {city}, {state} {s['zip']}",
                                    colour=wx_color_from_temp_f(first_hi_f if first_hi_f is not None else 70)
                                )
                                for (d, line, _sunrise, _sunset, _uv, _hi) in outlook:
                                    emb.add_field(name=d, value=line, inline=False)
                                emb.set_footer(text=f"Scheduled in {tz_name} • Units: {units}")
                                await user.send(embed=emb)
                                tz = _tzinfo_from_name(tz_name)
                                next_local = datetime.now(tz)
                                next_local = next_local.replace(hour=s["hh"], minute=s["mi"], second=0, microsecond=0)
                                if next_local <= datetime.now(tz):
                                    next_local += timedelta(days=7)
                                else:
                                    next_local += timedelta(days=7)
                                self.store.update_weather_sub(s["id"], channel_id=int(s["channel_id"]), next_run_utc=next_local.astimezone(timezone.utc).isoformat())
                        except Exception as e:
                            fallback = now_utc + timedelta(minutes=5)
                            self.store.update_weather_sub(s["id"], next_run_utc=fallback.isoformat())
                            await self.bot.get_channel(s["channel_id"]).send(f"\u26A0\ufe0f Weather error: {e} {traceback.format_exc()}")
        except Exception as e:
            await self.bot.get_channel(1468253598646534294).send(f"\u26A0\ufe0f Subscription error: {e} {traceback.format_exc()}")

    @events_scheduler.before_loop
    async def before_weather(self):
        await self.bot.wait_until_ready()

async def setup(bot: commands.Bot):
    await bot.add_cog(Events(bot))