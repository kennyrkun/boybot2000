import asyncio
import logging
import os
import re
import random
import traceback
import aiohttp
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List, Tuple

import discord
from discord.ext import tasks, commands
from discord import app_commands

logging.basicConfig(level = logging.INFO, format = "%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("NaturalLanguage")

class NaturalLanguage(commands.Cog):
	def __init__(self, bot: commands.Bot):
		self.bot = bot

		self.model = "gemma2:2b"
		self.ollamaUri = "http://ollama:11434"

		# TODO: skip this via environment variable
		# TODO: this fails due to unable to resolve host for some reason
		#request = requests.post(f"{self.ollamaUri}/api/show", json = {
		#	"model": self.model
		#})

		#response = request.json()

		#if response.get("license") is None:
		#	request = requests.post(f"{self.ollamaUri}/api/pull", json = {
		#		"model": self.model
		#	})

	def cog_unload(self):
		return

	def check_cog_enabled(self, guildId: int):
		return type(self).__name__ in self.bot.store.get_enabled_extensions(guildId)

	def cog_check(self, ctx):
		return self.check_cog_enabled(ctx.guild.id)

	def interaction_check(self, inter):
		return self.check_cog_enabled(inter.guild.id)

	# -------- Helper functions -------

	async def prompt(self, guildId: int, prompt: str) -> Optional[str]:
		if not self.check_cog_enabled(guildId):
			return None

		if not prompt:
			raise Exception("No prompt was provided to NaturalLanguage cog.")

		async with aiohttp.ClientSession() as session:
			async with session.post(f"{self.ollamaUri}/api/generate", json = {
				"model": self.model,
				"prompt": "You are a funny UWU redditor who loves being silly and using text based emotes. " + prompt,
				"stream": False,
			}) as request:
				if request.status != 200:
					raise RuntimeError(f"Prompt request returned {request.status}.")

		response = await request.json()

		if response.get("error") is not None:
			raise Exception("Error response from model: " + response.get("error"))
		elif response.get("response") is None:
			raise Exception("Response from model was None.")

		response = response.get("response").strip()

		response += f"\n-# This response was generated using {self.model}."

		return response

async def setup(bot: commands.Bot):
	await bot.add_cog(NaturalLanguage(bot))
