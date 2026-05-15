import sys
import discord
import samplerate as sampleRateLib
import pyaudio
import numpy as np
import subprocess
import asyncio
import logging

import discord
from discord.ext import tasks, commands
from discord import app_commands

logging.basicConfig(level = logging.INFO, format = "%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("radio")

subprocesses = []
tasks = set()

# I tried using discord.PCMAudio, but it doesn't work because PCMAudio expects 48khz but P25 only provides 8khz
class PCMAudioPlayer(discord.AudioSource):
    def __init__(self) -> None:
        logger.info("Starting PCMAudioPlayer.")

        self.audio  = pyaudio.PyAudio()
        self.device = self.audio.get_device_info_by_index(1)

        logger.info(f"Audio device: {self.device}")

        self.channels = self.device["maxInputChannels"]
        self.chunk    = int(self.device["defaultSampleRate"] * 0.02)
        self.ratio    = 48000 / self.device["defaultSampleRate"]
        self.stream   = self.audio.open(
            format             = pyaudio.paInt16,
            channels           = self.channels,
            rate               = int(self.device["defaultSampleRate"]),
            input              = True,
            input_device_index = self.device["index"],
            frames_per_buffer  = self.chunk,
        )

        if self.ratio != 1:
            logger.info("using resampler")
            self.resampler = sampleRateLib.Resampler("sinc_best", channels = 2)
        else:
            logger.info("NOT using resampler")
            self.resampler = None

        super().__init__()

    def read(self) -> bytes:
        frame = self.stream.read(self.chunk, exception_on_overflow=False)
        frame = np.frombuffer(frame, dtype = np.int16)

        frame = frame * (80 / 100)

        if self.channels == 1:
            frame = np.repeat(frame, 2)

        if self.resampler:
            # this is probably converting the 8khz audio into 48khz
            frame = np.stack((frame[::2], frame[1::2]) , axis=1)
            return self.resampler.process(frame, self.ratio).astype(np.int16).tobytes()

        return frame.tobytes()

    def __del__(self):
        logger.info("destroying PCMAudioPlayer")
        self.stream.close()

class Radio(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def cog_unload(self):
        return

    def check_cog_enabled(self, guildId: int):
        return type(self).__name__ in self.bot.store.get_enabled_extensions(guildId)

    def cog_check(self, ctx):
        return self.check_cog_enabled(ctx.guild.id)

    def interaction_check(self, inter):
        return self.check_cog_enabled(inter.guild.id)

    async def killSubprocesses():
        global subprocesses

        if len(subprocesses) == 0:
            logger.info("No subprocesses to shutdown.")
            return

        logger.info(f"Shutting down {len(subprocesses)} subprocesses...")

        for process in subprocesses:
            try:
                process.kill()
            except Exception as e:
                logger.info(f"Skipping subprocess kill because an exception was raised: {e}")
                pass

        subprocesses.clear()
        
        logger.info("All subprocesses shutdown.")

        logger.info("Canceling running tasks...")

        if len(tasks) == 0:
            logger.info("No tasks to cancel.")
            return

        logger.info(f"Shutting down {len(tasks)} tasks...")

        for task in tasks:
            try:
                task.cancel()
            except Exception as e:
                logger.info(f"Skipping task cancel because an exception was raised: {e}")
                pass

        tasks.clear()

    async def startOP25(self, inter: discord.Interaction, config):
        message = await inter.reply(f":clock12: Starting OP25 for {config}...", ephemeral = True)

        sdrProcess = await asyncio.create_subprocess_exec(
            "/home/sdr/op25/op25/gr-op25_repeater/apps/rx.py",
                "--trunk-conf-file", f"{config}.tsv",
                "--freq-error-tracking",
                "--nocrypt",
                "--vocoder",
                "--phase2-tdma",
                "--args", "rtl",
                "--gains", "lna:36",
                "--sample-rate", "960000",
                "--fine-tune", "500", # fine tune frequency offset
                "--freq-corr", "0",
                "--verbosity", "0",
                "--demod-type", "cqpsk",
                "--terminal-type", "http:192.168.0.9:8080",
                "--udp-player",
                "--audio-output", "hw:2,1",
            stdout = asyncio.subprocess.PIPE,
            stderr = asyncio.subprocess.STDOUT,
            cwd = "/home/sdr/op25/op25/gr-op25_repeater/apps/"
        )

        subprocesses.append(sdrProcess)

        await message.edit(content = ":clock1: Waiting for ALSA...")

        while sdrProcess.returncode is None:
            line = await sdrProcess.stdout.readline()

            if not line:
                continue

            line = line.decode()
            logger.info(line)

            if line.find("using ALSA sound system") != -1:
                await message.edit(content = ":clock2: ALSA is ready, starting stream...")
                await asyncio.sleep(3)
                break
            elif line.find("Traceback (most recent call last):") != -1:
                await message.edit(content = ":broken_heart: OP25 encountered a fatal error.")
                await disconnect(self.bot.voice_client)
                await killSubprocesses()
                return

        try:
            audioPlayer = PCMAudioPlayer()
        except Exception as e:
            logger.error(f"Failed to start PCMAudioPlayer: {e}")

            await disconnect(self.bot.voice_client)
            await message.edit(content = ":broken_heart: Failed to start PCMAudioPlayer.")
            return

        self.bot.voice_client.play(audioPlayer, after=lambda e: print(f'Player error: {e}') if e else None)

        await message.edit(content = f":white_check_mark: Streaming {config}.")

        await bot.change_presence(activity = 
            discord.Streaming(
                name = config,
                url = "https://github.com/boatbod/op25"
            )
        )

    async def rtlfmAudioProcessingLoop(sdrProcess, aplayProcess):
        logger.info("Starting RTLFM loop.")

        # loop should automatically exit when the tasks are killed?
        while sdrProcess.returncode is None and aplayProcess.returncode is None:
            line = await sdrProcess.stdout.read(1024)
            aplayProcess.stdin.write(line)

        logger.info("Ended RTLFM loop.")

    async def startRTLFM(inter: discord.Interacton, freq):
        message = await inter.reply(f":clock12: Starting RTLFM...", ephemeral = True)

        sdrProcess = await asyncio.create_subprocess_exec(
            "rtl_fm",
                "-f", "467612500",
                "-s", "44100",
                "-g", "9",
                "-l", "10",
                "-",
            stdout = asyncio.subprocess.PIPE,
            stderr = asyncio.subprocess.STDOUT
        )

        aplayProcess = await asyncio.create_subprocess_exec(
            "aplay",
                "-t", "raw",
                "-r", "44100",
                "-c", "1",
                "-f", "S16_LE",
                "-D", "hw:2,1",
            stdout = asyncio.subprocess.PIPE,
            stderr = asyncio.subprocess.STDOUT,
            stdin  = asyncio.subprocess.PIPE
        )

        subprocesses.append(sdrProcess)
        subprocesses.append(aplayProcess)

        asyncio.create_task(rtlfmAudioProcessingLoop(sdrProcess, aplayProcess))

        try:
            audioPlayer = PCMAudioPlayer()
        except Exception as e:
            logger.error(f"Failed to start PCMAudioPlayer: {e}")

            await disconnect(self.bot.voice_client)
            await message.edit(content = ":broken_heart: Failed to start PCMAudioPlayer.")
            return

        self.bot.voice_client.play(audioPlayer, after = lambda e: logger.error(f'Player error: {e}') if e else None)

        await message.edit(content = f":white_check_mark: Streaming FM {freq}.")

        await bot.change_presence(activity = 
            discord.Streaming(
                name = freq,
                url = "https://manpages.ubuntu.com/manpages/trusty/man1/rtl_fm.1.html"
            )
        )

    @app_commands.command(name = "play", help = "Join the current voice channel and play radio audio from a particular frequency or P25 zone.")
    async def play(self, inter: discord.Interaction):
        logger.info("play command")

        if inter.author.voice is None:
            raise commands.CommandError("You must connected to a voice channel.")

        if self.bot.voice_client is not None:
            await disconnect(self.bot.voice_client)

        try:
            await inter.author.voice.channel.connect()

            if self.bot.voice_client is None:
                raise commands.CommandError("[Probably 4006](https://github.com/Rapptz/discord.py/pull/10210)? :pensive:")
        except Exception as e:
            raise commands.CommandError(f"Failed to connect to voice channel: {e}.")

        logger.info(f"connected with args {args}")

        await killSubprocesses()

        if len(args) == 1:
            if args[0].isdigit():
                if len(args[0]) != 9:
                    raise commands.CommandError("Frequency is out of range.")

                raise commands.CommandError("Not yet, but soon!")

                await startRTLFM(inter, args[0])
                return
            else:
                if args[0] == "okwin":
                    await startOP25(inter, "okwin")
                    return
                elif args[0] == "okc":
                    await startOP25(inter, "okc")
                    return

        raise commands.CommandError("Invalid arguments.")

    @app_commands.command(name = "stop", help = "Disconnect bot")
    async def stop(self, inter: discord.Interaction):
        if self.bot.voice_client is None:
            return

        logger.info(f"{self.bot.voice_client}")

        await inter.reply("👋", ephemeral = True)
        await disconnect(self.bot.voice_client)

    @app_commands.event
    async def on_command_error(self, inter: discord.Interaction, error):
        await disconnect(self.bot.voice_client)
        await inter.reply(f"💔 {error}", ephemeral = True)
        logger.error(f"Error in command: {error}")

    @app_commands.event
    async def on_voice_state_update(self, member, before, after):
        if before.channel is None:
            return

        if member.id == bot.user.id:
            return

        # leave the channel if it becomes empty
        if len(before.channel.members) - 1 < 1:
            for client in bot.voice_clients:
                if client.channel.id == before.channel.id:
                    logger.info("Channel has become empty, leaving.")
                    await disconnect(client)

    async def disconnect(self, client):
        await client.disconnect()
        await killSubprocesses()

    async def setup(bot: commands.Bot):
        await bot.add_cog(Radio(bot))