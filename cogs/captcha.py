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

class BotCheck(discord.ui.View):
    def __init__(self):
        super().__init__()

        self.value = None

    @discord.ui.button(label = "Confirm", style = discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await interaction.followup.send("Yippee, you're in!")

        self.value = True

        await self.afterClick(interaction, button)

    @discord.ui.button(label = "Cancel", style = discord.ButtonStyle.grey)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await interaction.followup.send("Aw nuts, you gotta go!")

        self.value = False

        await self.afterClick(interaction, button)

    async def afterClick(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.stop() # stop the View from listening to more input.

        await interaction.followup.edit_message(message_id = interaction.message.id, content = "Are you a bot?", view = None)

class Captcha(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.timeout = 60

        self.captcha_scheduler.start()

    def cog_unload(self):
        self.captcha_scheduler.cancel()

    def check_cog_enabled(self, guild_id: int):
        return type(self).__name__ in self.bot.store.get_enabled_extensions(guild_id)

    def cog_check(self, ctx):
        if ctx.guild is None:
            return False

        return self.check_cog_enabled(ctx.guild.id)

    def interaction_check(self, inter):
        return self.check_cog_enabled(inter.guild.id)

    async def challengeMember(self, member: discord.Member):
        view = BotCheck(timeout = self.timeout)

        message = await member.send(f"Are you a bot? Answer in <t:{int((datetime.now() + timedelta(seconds = view.timeout)).timestamp())}:R>.", view = view)

        # Wait for the View to stop listening for input
        await view.wait()

        if view.value is None:
            await member.guild.kick(member)

            message.edit_message(content = "you're too slow!!!! :<<", view = None)
        elif view.value:
            self.bot.store.remove_captcha_user(member.id, member.guild.id)
        else:
            await member.guild.kick(member)

    # -------- Event handlers --------

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if self.bot.store is None:
            return

        if member.guild is None:
            return

        if not self.check_cog_enabled(member.guild.id):
            return

        # if the user is already in the captcha pending list, ignore them
        if member.id in self.bot.store.list_captcha_users(member.guild):
            return

        if self.bot.store.add_captcha_user(member.id, member.guild.id, datetime.utcnow()):
            await self.challengeMember(member)

    # --------- Text Commands --------

    @commands.command()
    async def challenge(self, ctx: commands.Context):
        # user might not have all the right variables, hopefully it is always a Member object.
        await self.challengeMember(ctx.author)
    

    # -------- Schedulers --------

    @tasks.loop(seconds = 60)
    async def captcha_scheduler(self):
        if self.bot.store is None:
            return
        
        try:
            queuedUsers = self.bot.store.list_captcha_users()

            timeoutTimestamp = datetime.utcnow() + timedelta(seconds = self.timeout)

            for user in queuedUsers:
                if user.timestamp > timeoutTimestamp:
                    # get guild from id and kick the user
                    guild = self.bot.fetch_guild(user.guild_id)

                    if guild is None:
                        raise RuntimeError("Unable to fetch guild {user.guild_id} for user {user.user_id} to kick them. User was past the timeout without captcha confirmation.")

                    guild.kick(user.user_id)

        except Exception as e:
            await self.bot.get_channel(1468253598646534294).send(f"\u26A0\ufe0f Captcha error: {e}\n{traceback.format_exc()}")

    @captcha_scheduler.before_loop
    async def before_captcha(self):
        await self.bot.wait_until_ready()

async def setup(bot: commands.Bot):
    await bot.add_cog(Captcha(bot))