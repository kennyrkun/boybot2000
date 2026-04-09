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

__all__: tuple[str, ...] = ("MyLayoutView",)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("captcha")

class UserJoinChallengeView(discord.ui.LayoutView):
    count = 0
    message: discord.Message | None = None
    container = discord.ui.Container["MyLayoutView"](
        discord.ui.Section(
            "## OKC Community Verification",
            "Click the button that says ",
            accessory=discord.ui.Thumbnail["MyLayoutView"]("https://i.imgur.com/9sDnoUW.jpeg"),
        ),
        accent_color=discord.Color.blurple(),
    )
    row: discord.ui.ActionRow[MyLayoutView] = discord.ui.ActionRow()

    def __init__(self, user: discord.User | discord.Member, timeout: float = 60.0) -> None:
        super().__init__(timeout=timeout)
        self.user = user

    # this method should return True if all checks pass, else False is returned
    async def interaction_check(self, interaction: discord.Interaction[discord.Client]) -> bool:
        if interaction.user == self.user:
            return True
        
        await interaction.response.send_message(f"The command was initiated by {self.user.mention}", ephemeral=True)
        return False

    # this method is called when the period mentioned in timeout kwarg passes.
    async def on_timeout(self) -> None:
        for child in self.walk_children():
            if isinstance(child, discord.ui.Button):
                child.disabled = True

        if self.message:
            await self.message.edit(view=self)

    # adding a component using its decorator
    @row.button(label="0", style=discord.ButtonStyle.green)
    async def counter(self, inter: discord.Interaction, button: discord.ui.Button[MyLayoutView]) -> None:
        self.count += 1
        button.label = str(self.count)
        await inter.response.edit_message(view=self)

    # error handler for the view
    async def on_error(
        self, interaction: discord.Interaction[discord.Client], error: Exception, item: discord.ui.Item[typing.Any]
    ) -> None:
        tb = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        message = f"An error occurred while processing the interaction for {str(item)}:\n```py\n{tb}\n```"
        await interaction.response.send_message(message)

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
    async def challenge(self, ctx):
        view = UserJoinChallengeView(ctx.author)
        view.message = await ctx.send()

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