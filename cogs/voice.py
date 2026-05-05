import os
import discord
from discord.ext import commands
import asyncio
import logging

logger = logging.getLogger("discord.tedomi.voice")


class Voice(commands.Cog):
    def __init__(self, bot, voice_channel_id):
        self.bot = bot
        self.voice_channel_id = voice_channel_id

    async def connect_to_voice(self):
        channel = self.bot.get_channel(self.voice_channel_id)

        if not channel or not isinstance(channel, discord.VoiceChannel):
            logger.warning("Channel not found or is not a voice channel.")
            return None

        for vc in self.bot.voice_clients:
            if vc.channel.id == self.voice_channel_id:
                if vc.is_connected():
                    return vc
                await vc.disconnect()
                break

        try:
            voice_client = await channel.connect(
                timeout=60.0, reconnect=True, self_deaf=True, self_mute=True
            )
            logger.info(f"Successfully joined {channel.name}")
            return voice_client
        except Exception as e:
            logger.error(f"Failed to connect to {channel.name}: {e}")
            raise

    async def ensure_voice_connection(self):
        if self.bot.is_closed():
            return

        if any(
            vc.channel.id == self.voice_channel_id and vc.is_connected()
            for vc in self.bot.voice_clients
        ):
            return

        delay = 5
        while not self.bot.is_closed():
            try:
                await self.connect_to_voice()
                return
            except Exception:
                logger.warning(f"Reconnect attempt failed. Retrying in {delay} seconds...")
                await asyncio.sleep(delay)
                delay = min(delay * 2, 60)

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info(f"{self.bot.user} is online!")
        await self.ensure_voice_connection()

    @commands.Cog.listener()
    async def on_disconnect(self):
        logger.warning("Bot has been disconnected from Discord. Voice reconnect will resume after gateway reconnection.")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member == self.bot.user and before.channel is not None and after.channel is None:
            logger.warning("Bot was disconnected from the voice channel. Attempting to reconnect...")
            await self.ensure_voice_connection()

async def setup(bot):
    voice_channel_id_str = os.getenv("VOICE_CHANNEL_ID")
    if voice_channel_id_str is None:
        raise RuntimeError("VOICE_CHANNEL_ID environment variable is required for the Voice cog")

    try:
        voice_channel_id = int(voice_channel_id_str)
    except ValueError as exc:
        raise ValueError("VOICE_CHANNEL_ID must be an integer") from exc

    await bot.add_cog(Voice(bot, voice_channel_id))
