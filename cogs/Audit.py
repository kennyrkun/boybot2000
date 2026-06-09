import asyncio
import logging
import os
import re
import random
import traceback
import base64
import requests
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

        self.regex = re.compile(r"((t|b)+o+(y|t)( ?)+){2}", re.IGNORECASE)

    def cog_unload(self):
        return

    def check_cog_enabled(self, guildId: int):
        return type(self).__name__ in self.bot.store.get_enabled_extensions(guildId)

    def cog_check(self, ctx):
        return self.check_cog_enabled(ctx.guild.id)

    def interaction_check(self, inter):
        return self.check_cog_enabled(inter.guild.id)

    async def replyToMessage(self, message: discord.Message, prompt: str):
        promptData = {
            "prompt": prompt,
            "content": message.content,
            "images": []
        }

        for attachment in message.attachments:
            # TODO: check attachment.type make sure it's an image
            log.info("Downloading an image...")
            
            promptData["images"].append(
                base64.b64encode(requests.get(attachment.url).content).decode("utf-8")
            )

        response = await self.bot.NaturalLanguage.prompt(message.channel, {
                "prompt": "Reply to the following message.",
                "content": message.content,
                "images": []
            }) or "<:boykisser_sip:1488616986677084322>"

        return response

    # -------- Event listeners -------

    # TODO: listen for message edits, if the message is something we've already replied to, re-read the message and reply again?

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.guild is None:
            return

        if not self.check_cog_enabled(message.guild.id):
            return

        # TODO: this may not be required since we're using discord.Bot
        if message.author.id == self.bot.user.id:
            return

        messageText = message.content.casefold().strip().replace(" ", "")

        # waits just a little bit so that typing doesn't show up immediately.
        await asyncio.sleep(random.randint(0, 2))

        if message.reference is not None and isinstance(message.reference.resolved, discord.Message):
            if message.reference.resolved.author.id == self.bot.user.id:
                async with message.channel.typing():
                    await asyncio.sleep(random.randint(0, 4))

                    response = await self.replyToMessage(message, "Reply to this message") or "<:boykisser_sip:1488616986677084322>"

                    return await message.reply(response, mention_author = True)

        # if they said boybot
        elif self.regex.search(messageText) or f"<@{self.bot.user.id}>" in messageText:
            await asyncio.sleep(random.randint(0, 4))

            if any(x in messageText for x in [ "good", "great", "thank", "smart", "cool", "awesome", "amazing", "perfect", "cute", "handsome", "yay", "best", "nice" ]):
                return await message.add_reaction("<:boykisser_pat:1488616985502810336>")
            elif any(x in messageText for x in [ "bad", "dumb", "stupid", "idiot", "dipshit", "retard", "fuck", "ass", "ugly", "ass" ]):
                return await message.add_reaction("<:boykisser_mad_as_hell:1488617115694006352>")
            else:
                async with message.channel.typing():
                    response = await self.replyToMessage(message, 
                    """
                        You will be given a message to read. If the message is directed AT you, reply to it normally.
                        If the message is talking ABOUT you, but not directly to you, reply with only and exactly with "Indirect" and nothing else. Otherwise, reply normally.
                    """)

                    if response and response != "Indirect":
                        return await message.reply(response, mention_author = True)

                    return await message.add_reaction("<:boykisser_what:1483293684899381248>")

        elif any(x in messageText for x in [ "clanker", "burger king" ]):
            return await message.add_reaction("<:boykisser_mad_as_hell:1488617115694006352>")
        
        # TODO: had to remove "boy" from this because it would reply to boykisser emotes
        elif any(x in messageText for x in [ "boys" ]):
            async with message.channel.typing():
                await asyncio.sleep(random.randint(0, 4))

            return await message.reply(
                    await self.replyToMessage(message, "If the message is talking about boys, reply with how much you love boys. PLEASE make sure the message is talking about boys 18 years and older.")
                or 
                    "i luv boys <:boykisser_meow:1488616984592781545>",
                mention_author = True
            )

        # sometimes, just type a little bit but don't say anything. like he changed his mind.
        if random.randint(0, 1000) < 5:
            return await message.channel.typing()

async def setup(bot: commands.Bot):
    await bot.add_cog(Boytoy(bot))