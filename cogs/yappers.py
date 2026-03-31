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
        
        if self.store is None:
            log.error("Storage backend not available.")

    def cog_unload(self):
        return

    # -------- Event listeners -------

    @commands.Cog.listener()
    async def on_message(self, message):
        self.store.increment_yaps(message.author.id, message.guild.id)

    # ------- Slash commands -------

    @app_commands.command(name = "top_yappers", description = "List the top yappers in this server.")
    async def top_yappers(self, inter: discord.Interaction):
        await inter.response.defer()
        await inter.followup.send(content = self.store.get_top_yappers(5))

async def setup(bot: commands.Bot):
    await bot.add_cog(Yappers(bot))
