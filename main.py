import os
import asyncio
import logging
from typing import Optional

import discord
from discord.ext import commands
from discord import app_commands

from store import Store

TOKEN = os.getenv("DISCORD_TOKEN")
APP_ID = os.getenv("DISCORD_APP_ID") # optional
DB_PATH = os.getenv("WEATHER_DB_PATH") or "data/weather.sqlite3"

logging.basicConfig(level = logging.INFO, format = "%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("boybot2000")

intents = discord.Intents.default() # change this if more intents are needed
intents.message_content = True
intents.guild_scheduled_events = True
intents.guilds = True
intents.members = True

class boybot2000(commands.Bot):
    async def on_ready():
        log.info("Logged in as %s (%s)", bot.user, bot.user.id)

    async def setup_hook(self) -> None:
        self.store = Store(DB_PATH)

        await self.load_extension("cogs.boytoy")
        await self.load_extension("cogs.captcha")
        await self.load_extension("cogs.events")
        await self.load_extension("cogs.moon")
        #await self.load_extension("cogs.radio")
        await self.load_extension("cogs.weather")
        await self.load_extension("cogs.yappers")

        try:
            synced = await self.tree.sync()
            log.info("Synced %d app commands globally.", len(synced))
        except Exception:
            log.exception("Failed to sync app commands.")

    @app_commands.command(name = "cogs", description = "Restarts the bot")
    @commands.has_permissions(administrator = True)
    @app_commands.choices(option = [
        app_commands.Choice(name = "enable", value = 1),
        app_commands.Choice(name = "disable", value = 0),
    ])
    async def cogs(self, inter: discord.Interaction, option: Optional[app_commands.Choice[int]] = None,  cogName: Optional[str] = None) -> None:
        await inter.response.defer()

        # TODO: verify cog name

        if options is None:
            strings = ""
            for cogs in self.store.get_enabled_cogs(inter.guild.id):
                strings += f"{cog}\n"

            return inter.followup.send("**Enabled cogs**:\n" + strings, ephemeral = True)

        if cogName is None:
            return await inter.followup.send("Cog name is required when option is provided.")

        if option:
            if self.store.enable_cog(inter.guild.id):
                return await inter.followup.send(f"Enabled cog {cogName} for this server.", ephemeral = True)
            else:
                return await inter.followup.send(f"Failed to enable cog {cogName} for this server.", ephemeral = True)
        else:
            if self.store.disable_cog(inter.guild.id):
                return await inter.followup.send(f"Disabled cog {cogName} for this server.", ephemeral = True)
            else:
                return await inter.followup.send(f"Failed to disable cog {cogName} for this server.", ephemeral = True)

    @app_commands.command(name = "restart", description = "Restarts the bot")
    @commands.has_permissions(administrator = True)
    async def restart(self, inter: discord.Interaction) -> None:
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

    async with bot:
        await bot.start(TOKEN)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
