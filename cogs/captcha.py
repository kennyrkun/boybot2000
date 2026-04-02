import os
import asyncio
import traceback
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List, Tuple

import discord
from discord.ext import tasks, commands
from discord import app_commands

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("captcha")

class Captcha(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        # Try to discover the Store from bot or import-time fallback
        self.store = getattr(bot, "store", None)
        
        if self.store is None:
            log.error("Storage backend not available.")

        self.captcha_scheduler.start()

    def cog_unload(self):
        self.captcha_scheduler.cancel()

    # -------- Event handlers -------

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if self.store is None:
            return

    # -------- Schedulers --------

    @tasks.loop(seconds=60)
    async def captcha_scheduler(self):
        if self.store is None:
            return
        
        try:
            return
        except Exception as e:
            await self.bot.get_channel(1468253598646534294).send(f"\u26A0\ufe0f Captcha error: {e}\n{traceback.format_exc()}")

    @captcha_scheduler.before_loop
    async def before_captcha(self):
        await self.bot.wait_until_ready()

async def setup(bot: commands.Bot):
    await bot.add_cog(Captcha(bot))