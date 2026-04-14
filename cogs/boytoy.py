import asyncio
import logging
import os
import re
import random
import traceback
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

        self.regex = re.compile(r"((t|b)+o+(y|t)( ?)+){2}", re.IGNORECASE)

    def cog_unload(self):
        return

    def cog_check(self, ctx):
        if ctx.guild.id in self.bot.store.get_enabled_cogs(ctx.guild.id):
            return False

        return True

    def interaction_check(self, inter):
        if inter.guild.id in self.bot.store.get_enabled_cogs(inter.guild.id):
            return False

        return True

    # -------- Event listeners -------

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.id == self.bot.user.id:
            return

        messageText = message.content.casefold().strip().replace(" ", "")

        # waits just a little bit so that typing doesn't show up immediately.
        await asyncio.sleep(random.randint(0, 2))

        if message.reference is not None and isinstance(message.reference.resolved, discord.Message):
            if message.reference.resolved.author.id == self.bot.user.id:
                async with message.channel.typing():
                    await asyncio.sleep(random.randint(0, 4))

                return await message.reply("<:boykisser_sip:1488616986677084322>", mention_author = True)

        elif self.regex.search(messageText):
            await asyncio.sleep(random.randint(0, 4))

            if any(x in messageText for x in [ "good", "great", "thank", "smart", "cool", "awesome", "amazing", "perfect", "cute", "handsome", "yay", "best", "nice" ]):
                return await message.add_reaction("<:boykisser_pat:1488616985502810336>")
            elif any(x in messageText for x in [ "bad", "dumb", "stupid", "idiot", "dipshit", "retard", "fuck", "ass", "ugly", "ass" ]):
                return await message.add_reaction("<:boykisser_mad_as_hell:1488617115694006352>")
            else:
                return await message.add_reaction("<:boykisser_what:1483293684899381248>")
        
        # TODO: had to remove "boy" from this because it would reply to boykisser emotes
        elif any(x in messageText for x in [ "boys" ]):
            async with message.channel.typing():
                await asyncio.sleep(random.randint(0, 4))

            return await message.reply("i luv boys <:boykisser_meow:1488616984592781545>", mention_author = True)

        # sometimes, just type a little bit but don't say anything. like he changed his mind.
        if random.randint(0, 1000) < 10:
            return await message.channel.typing()

async def setup(bot: commands.Bot):
    await bot.add_cog(Boytoy(bot))
