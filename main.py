import os
import asyncio
import logging

import discord
from discord.ext import commands
from discord import app_commands

from store import Store

TOKEN = os.getenv("DISCORD_TOKEN")
APP_ID = os.getenv("DISCORD_APP_ID") # optional
WEATHER_DB_PATH = os.getenv("WEATHER_DB_PATH") or "data/weather.sqlite3"

logging.basicConfig(level = logging.INFO, format = "%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("boybot2000")

intents = discord.Intents.default() # change this if more intents are needed
intents.message_content = True
intents.guild_scheduled_events = True

class boybot2000(commands.Bot):
    async def setup_hook(self) -> None:
        await self.load_extension("cogs.weather")
        await self.load_extension("cogs.events")
        await self.load_extension("cogs.moon")
        await self.load_extension("cogs.boytoy")

        try:
            synced = await self.tree.sync()
            log.info("Synced %d app commands globally.", len(synced))
        except Exception:
            log.exception("Failed to sync app commands.")

    @app_commands.command(name = "restart", help = "Restarts the bot")
    @app_commands.has_permissions(administrator = True)
    async def restart(self):
        exit()

async def main():
    if not TOKEN:
        raise SystemExit("Missing DISCORD_TOKEN in environment.")

    bot_kwargs = dict(intents = intents)

    if APP_ID:
        try:
            bot_kwargs["application_id"] = int(APP_ID)
        except ValueError:
            log.warning("DISCORD_APP_ID is set but not an int; ignoring.")

    bot = boybot2000(command_prefix = "!", **bot_kwargs)

    # Attach store to bot so cogs can use it
    bot.store = Store(WEATHER_DB_PATH)

    @bot.event
    async def on_ready():
        log.info("Logged in as %s (%s)", bot.user, bot.user.id)

    async with bot:
        await bot.start(TOKEN)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
