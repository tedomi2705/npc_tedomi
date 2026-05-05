import os
import discord
from discord.ext import commands
import asyncio
import logging

logger = logging.getLogger("discord.tedomi.voice")


class SilenceAudioSource(discord.AudioSource):
    def __init__(self, duration_ms=360):
        self.frames = int(duration_ms / 20)  # 20ms per frame
        self.sent = 0

    def read(self):
        if self.sent >= self.frames:
            return b""  # stop after duration

        self.sent += 1
        return b"\x00" * 3840  # 20ms frame

    def is_opus(self):
        return False


class Voice(commands.Cog):
    def __init__(self, bot, voice_channel_id):
        self.bot = bot
        self.voice_channel_id = voice_channel_id
        self.task = None

    async def connect(self):
        channel = self.bot.get_channel(self.voice_channel_id)
        if not isinstance(channel, discord.VoiceChannel):
            logger.warning("Invalid voice channel")
            return None

        # reuse existing connection if present
        for vc in self.bot.voice_clients:
            if vc.channel.id == self.voice_channel_id:
                return vc

        return await channel.connect(reconnect=True)

    async def burst_loop(self):
        await self.bot.wait_until_ready()

        while not self.bot.is_closed():
            try:
                vc = await self.connect()

                if vc and vc.is_connected() and not vc.is_playing():
                    vc.play(SilenceAudioSource(duration_ms=100))

                await asyncio.sleep(36)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Voice loop error: {e}")
                await asyncio.sleep(5)

    @commands.Cog.listener()
    async def on_ready(self):
        if self.task is None:
            self.task = asyncio.create_task(self.burst_loop())

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member == self.bot.user and after.channel is None:
            logger.warning("Disconnected from voice, reconnecting...")
            await asyncio.sleep(2)  # small delay helps stability
            await self.connect()


async def setup(bot):
    voice_channel_id_str = os.getenv("VOICE_CHANNEL_ID")
    if voice_channel_id_str is None:
        raise RuntimeError(
            "VOICE_CHANNEL_ID environment variable is required for the Voice cog"
        )

    try:
        voice_channel_id = int(voice_channel_id_str)
    except ValueError as exc:
        raise ValueError("VOICE_CHANNEL_ID must be an integer") from exc

    await bot.add_cog(Voice(bot, voice_channel_id))
