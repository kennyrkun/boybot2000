import os
import asyncio
import typing
import traceback
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List, Tuple

import discord
from discord.ext import tasks, commands
from discord import app_commands

logging.basicConfig(level = logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("captcha")

class Confirm(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.value = None

    # When the confirm button is pressed, set the inner value to `True` and
    # stop the View from listening to more input.
    # We also send the user an ephemeral message that we're confirming their choice.
    @discord.ui.button(label='Confirm', style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message('Confirming', ephemeral=True)
        self.value = True
        self.stop()

    # This one is similar to the confirmation button except sets the inner value to `False`
    @discord.ui.button(label='Cancel', style=discord.ButtonStyle.grey)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message('Cancelling', ephemeral=True)
        self.value = False
        self.stop()

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

    def cog_check(self, ctx):
        if ctx.guild.id in self.bot.store.get_enabled_cogs(ctx.guild.id):
            return False

        return True

    def interaction_check(self, inter):
        if inter.guild.id in self.bot.store.get_enabled_cogs(inter.guild.id):
            return False

        return True

    # -------- Event handlers --------

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if self.store is None:
            return

    # --------- Text Commands --------

    @commands.command()
    async def challenge(self, ctx: commands.Context):
        # We create the view and assign it to a variable so we can wait for it later.
        view = Confirm()
        await ctx.send('Do you want to continue?', view=view)
        # Wait for the View to stop listening for input...
        await view.wait()
        if view.value is None:
            print('Timed out...')
        elif view.value:
            print('Confirmed...')
        else:
            print('Cancelled...')

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