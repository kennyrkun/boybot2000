import os
import asyncio
import traceback
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List, Tuple

import discord
from discord.ext import tasks, commands
from discord import app_commands

logging.basicConfig(level = logging.INFO, format = "%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("yappers")

class Yappers(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        # Try to discover the Store from bot or import-time fallback
        self.store = getattr(bot, "store", None)

        self.topYappers = {}
        
        if self.store is None:
            log.error("Storage backend not available.")

    def cog_unload(self):
        return

    # -------- Event listeners -------

    @commands.Cog.listener()
    async def on_message(self, message):
        newTopYappers = self.store.increment_yaps(message.author.id, message.guild.id)

        if message.guild.id in self.topYappers:
            # use the length of old top yappers because the new list could be longer
            for x in range(0, len(self.topYappers[message.guild.id]) - 1):
                if self.topYappers[message.guild.id][x]["user_id"] != newTopYappers[x]["user_id"]:
                    await message.reply(content = "You are this server's new #{x + 1} top yapper with {newTopYappers[x]['message_count']} messages!")
                    break

        self.topYappers[message.guild.id] = newTopYappers

    # ------- Slash commands -------

    @app_commands.command(name = "top_yappers", description = "List the top yappers in this server.")
    async def top_yappers(self, inter: discord.Interaction):
        await inter.response.defer()

        string = "**Top yappers:**\n"

        for yapper in self.store.get_top_yappers(inter.guild.id):
            string += f"<@{yapper['user_id']}>: {yapper['message_count']}\n"

        await inter.followup.send(content = string, ephemeral = True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Yappers(bot))
