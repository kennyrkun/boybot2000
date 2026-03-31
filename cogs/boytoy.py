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
        if message.author.id == self.bot.user.id:
            return

        messageText = message.content.casefold()

        if message.reference is not None and isinstance(message.reference.resolved, discord.Message):
            if message.reference.resolved.author.id == self.bot.user.id:
                await message.reply("<:boykisser_sip:1488616986677084322>", mention_author = True)

        elif any(x in messageText for x in [ "boy bot", "boybot", "boybot2000", "boy bot 2000", "boybot 2000" ]):
            if any(x in messageText for x in [ "good", "great", "thank" ]):
                await message.add_reaction("<:boykisser_pat:1488616985502810336>")
            elif any(x in messageText for x in [ "bad", "dumb", "stupid", "idiot", "dipshit", "retard", "fuck", "ass" ]):
                await message.add_reaction("<:boykisser_mad_as_hell:boykisser_mad_as_hell>")
            else:
                await message.add_reaction("<:boykisser_what:1483293684899381248>")
        
        elif "boys" in message.content:
            await message.reply("i luv boys <:boykisser_meow:1488616984592781545>", mention_author = True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Boytoy(bot))
