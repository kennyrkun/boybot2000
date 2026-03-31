import os
import asyncio
import traceback
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List, Tuple

import discord
from discord.ext import tasks, commands
from discord import app_commands

logging.basicConfig(level = logging.INFO, format = "%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("boytoy")

class Boytoy(commands.Cog):
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
        if message.author.id == self.user.id:
            return

        if message.reference is not None and isinstance(message.reference.resolved, discord.Message):
            if message.reference.resolved.author.id == self.user.id:
                await message.reply("<:boykisser_meow:1485641863024087101>", mention_author = True)
                return

        if "boybot" in message.content or "boybot2000" in message.content:
            await message.add_reaction("<:boykisser_meow:1485641863024087101>")
            return
        
        if "boys" in message.content:
            await message.reply("i luv boys <:boykisser_meow:1485641863024087101>", mention_author = True)
            return

async def setup(bot: commands.Bot):
    await bot.add_cog(Boytoy(bot))
