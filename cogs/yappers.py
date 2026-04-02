import os
import asyncio
import traceback
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List, Tuple
from sqlite3 import IntegrityError

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
        if message.author.id == self.bot.user.id:
            return

        if message.guild is None or message.guild.id not in self.store.list_yap_subs():
            return

        newTopYappers = self.store.increment_yaps(message.author.id, message.guild.id)

        if message.guild.id in self.topYappers:
            # use the length of old top yappers because the new list could be longer
            for x in range(0, len(self.topYappers[message.guild.id]) - 1):
                if self.topYappers[message.guild.id][x]["user_id"] != newTopYappers[x]["user_id"]:
                    await message.reply(
                        content = 
                        f"uwu!! {message.author.display_name} is the server's new #{x + 1} top yapper with {newTopYappers[x]['message_count']} messages! yap yap yap!\n" +
                        "-# This message will self-destruct in <t:{int((datetime.now() + timedelta(minutes=1)).timestamp())}:R>",
                        delete_after = 60
                    )
                    break

        self.topYappers[message.guild.id] = newTopYappers

    # ------- Slash commands -------

    @app_commands.command(name = "yap_subscribe", description = "Subscribe this guild to top yapper announcements.")
    @commands.has_permissions(administrator = True)
    async def yap_subscribe(self, inter: discord.Interaction,):
        if self.store is None:
            return await inter.response.send_message("Storage backend not available.", ephemeral = True)
        
        await inter.response.defer(ephemeral = True)

        try:
            self.store.add_yap_sub(inter.guild.id)
            await inter.followup.send(f":white_check_mark: Subscribed this server to top yapper annoucements.", ephemeral = True)
        except IntegrityError:
            await inter.followup.send(f"This server is already subscribed to top yapper annoucements!", ephemeral = True)
        except Exception as e:
            await inter.followup.send(f"\u26A0\ufe0f {type(e).__name__}: {e}\n{traceback.format_exc()}", ephemeral = True)

    @app_commands.command(name = "yap_unsubscribe", description = "Unsubscribe the current guild from top yapper annoucements.")
    async def yap_unsubscribe(self, inter: discord.Interaction):
        if self.store is None:
            return await inter.response.send_message("Storage backend not available.", ephemeral = True)

        await inter.response.defer(ephemeral = True)

        ok = self.store.remove_yap_sub(inter.guild.id)

        await inter.followup.send(f":white_check_mark: This server has been unsubscribed from top yapper announcements." if ok else f"Failed to cancel top yapper subscription for this server.", ephemeral = True)

    @app_commands.command(name = "top_yappers", description = "List the top yappers in this server.")
    async def top_yappers(self, inter: discord.Interaction):
        await inter.response.defer()

        if inter.guild is None or inter.guild.id not in self.store.list_yap_subs():
            await inter.followup.send("This server is not subscribed to top yapper announcements.", ephemeral = True)
            return

        topYappers = self.store.get_top_yappers(inter.guild.id)

        if len(topYappers) < 1:
            await inter.followup.send("This server does not have any yappers yet!")
            return

        string = "**Top yappers:**\n"

        for yapper in topYappers:
            string += f"<@{yapper['user_id']}>: {yapper['message_count']}\n"

        await inter.followup.send(content = string, ephemeral = True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Yappers(bot))
