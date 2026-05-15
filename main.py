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

class ExtensionManager(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    group = app_commands.Group(name = "extensions", description = "Manage extensions this bot can use in this server.")

    @group.command(name = "on", description = "Enables a particular extension.")
    # TODO: add auto-complete options using list of files in cogs folder
    @app_commands.checks.has_permissions(administrator = True)
    async def on(self, inter: discord.Interaction,  extension: str) -> None:
        if await self.verifyExtensionName(inter, extension) and self.bot.store.enable_extension(inter.guild.id, extension):
            return await inter.followup.send(f"Enabled extension {extension} for this server.", ephemeral = True)
        else:
            return await inter.followup.send(f"Failed to enable extension {extension} for this server.", ephemeral = True)

    @group.command(name = "off", description = "Disables a particular extension.")
    # TODO: add auto-complete options using list of files in cogs folder
    @app_commands.checks.has_permissions(administrator = True)
    async def off(self, inter: discord.Interaction,  extension: str) -> None:
        if await self.verifyExtensionName(inter, extension) and self.bot.store.disable_extension(inter.guild.id, extension):
            return await inter.followup.send(f"Disabled extension {extension} for this server.", ephemeral = True)
        else:
            return await inter.followup.send(f"Failed to disable extension {extension} for this server.", ephemeral = True)

    async def verifyExtensionName(self, inter: discord.Interaction, extensionName: str) -> bool:
        await inter.response.defer(ephemeral = True)

        # TODO: just check if the file exists in the cogs folder
        if extensionName in self.bot.availableCogs:
            return True

        return False

class boybot2000(commands.Bot):
    async def on_ready(self):
        log.info("Logged in as %s (%s)", self.user, self.user.id)

    async def setup_hook(self) -> None:
        self.store = Store(DB_PATH)

        await self.add_cog(ExtensionManager(self))

        # Natural Language must go first, because it is added to every cog including itself
        self.availableCogs = [ "NaturalLanguage", "Boytoy", "Captcha", "Events", "Moon", "Radio", "Weather", "Yappers" ]

        natLangCog = self.get_cog("cogs.NaturalLanguage")

        for cog in self.availableCogs:
            await self.load_extension(f"cogs.{cog}")

            cog = self.get_cog(f"cogs.{cog}")

            setattr(cog, "NaturalLanguage", natLangCog)

        try:
            synced = await self.tree.sync()
            log.info("Synced %d app commands globally.", len(synced))
        except Exception:
            log.exception("Failed to sync app commands.")

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

    # if your setup is configured to restart the process, this is effectively a restart.
    @bot.command(name = "stop", description = "Stops the bot.")
    @app_commands.checks.has_permissions(administrator = True)
    async def restart(inter: discord.Interaction) -> None:
        raise SystemExit("Stop requested.") # TODO: log by whom

    async with bot:
        await bot.start(TOKEN)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
