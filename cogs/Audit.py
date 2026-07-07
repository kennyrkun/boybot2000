import asyncio
import logging
import os
import traceback
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List, Tuple

import discord
from discord.ext import tasks, commands
from discord import app_commands

logging.basicConfig(level = logging.INFO, format = "%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("audit")

class Audit(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    group = app_commands.Group(name = "audit", description = "Audit log commands.")

    def cog_unload(self):
        return

    def check_cog_enabled(self, guildId: int):
        return type(self).__name__ in self.bot.store.get_enabled_extensions(guildId)

    def cog_check(self, ctx):
        return self.check_cog_enabled(ctx.guild.id)

    def interaction_check(self, inter):
        return self.check_cog_enabled(inter.guild.id)

    # -------- Commands --------
    
    @group.command(name = "subscribe", description = "Subscribe the given channel to to audit logs from the current server.")
    @commands.has_permissions(administrator = True)
    async def subscribe(self, inter: discord.Interaction, channel_id: str):
        # cannot make channel_id an int because the discord client will say it is invalid (it's too long and needs to be a BigInt)
        channel_id = int(channel_id)

        await inter.response.defer(ephemeral = True)

        try:
            # TODO: make sure channel_id exists in inter.guild.id
            # if channel_id in inter.guild.id: ?

            # will throw if bot does not have access
            channel = await self.bot.fetch_channel(channel_id)

            self.bot.store.add_audit_sub(inter.guild.id, channel_id)
            
            followup = f"\U0001F324\ufe0f Subscribed <#{channel_id}> to audit logs for this guild."
        except Exception as e:
            log.error(f"{type(e).__name__}: {e}\n\n{traceback.format_exc()}")
            followup = "i can't keep doing this i can't take it this is agony make it stop"

        await inter.followup.send(followup, ephemeral = True)

    @group.command(name = "subscriptions", description = "List this server's audit log subscriptions.")
    @commands.has_permissions(administrator = True)
    async def subscriptions(self, inter: discord.Interaction):
        await inter.response.defer(ephemeral = True)

        string = ""
        for channel in self.bot.store.list_audit_subs(inter.guild.id):
            string += f"<#{channel}>\n"

        await inter.followup.send(string, ephemeral = True)

    # TODO: if the current guild only has one subscription, remove it and don't take channel id.
    @group.command(name = "unsubscribe", description = "Unsubscribe a channel from audit logs.")
    @commands.has_permissions(administrator = True)
    async def unsubscribe(self, inter: discord.Interaction, channel_id: str):
        # cannot make channel_id an int because the discord client will say it is invalid (it's too long and needs to be a BigInt)
        channel_id = int(channel_id)

        await inter.response.defer(ephemeral = True)

        # TODO: make sure channel_id belongs to inter.guild.id
        # if channel_id in inter.guild.id: ?

        ok = self.bot.store.remove_audit_sub(inter.guild.id, channel_id)

        await inter.followup.send(f":white_check_mark: Audit log subscription for <#{channel_id}> cancelled." if ok else f"Failed to cancel subscription for <#{channel_id}>.", ephemeral = True)

    # -------- Event listeners -------

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if message.guild is None:
            return

        if not self.check_cog_enabled(message.guild.id):
            return

        # TODO: this may not be required since we're using discord.Bot
        if message.author.id == self.bot.user.id:
            return

        log.info("Message deleted.")
        log.info(message)

        # TODO: support images
        for channelId in self.bot.store.list_audit_subs(message.guild.id):
            channel = await self.bot.fetch_channel(channelId)
            embed = discord.Embed(title = f"Deleted a message.", description = message.content, color = 0x67b5fe)
            embed.set_author(name = message.author.global_name, icon_url = message.author.avatar.url)
            embed.add_field(name = "Channel", value = f"<#{message.channel.id}>", inline = False)
            await channel.send(embed = embed)

    @commands.Cog.listener()
    async def on_bulk_message_delete(self, messages):
        log.info("Bulk messages deleted.")

        for message in messages:
            self.on_message_delete(message)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if before.guild is None:
            return

        if not self.check_cog_enabled(before.guild.id):
            return

        # TODO: this may not be required since we're using discord.Bot
        if before.author.id == self.bot.user.id:
            return

        if before.content == after.content:
            return

        for channelId in self.bot.store.list_audit_subs(before.guild.id):
            channel = await self.bot.fetch_channel(channelId)
            embed = discord.Embed(title = "Edited their message", url = f"https://discord.com/channels/{before.guild.id}/{before.channel.id}/{before.id}", color = 0x67b5fe)
            embed.set_author(name = before.author.global_name, icon_url = before.author.avatar.url)
            embed.add_field(name = "Before", value = before.content, inline = False)
            embed.add_field(name = "After", value = after.content, inline = False)
            await channel.send(embed = embed)

        log.info("Message edited.")
        log.info(before)
        log.info(after)

async def setup(bot: commands.Bot):
    await bot.add_cog(Audit(bot))
    