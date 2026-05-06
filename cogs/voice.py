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
    def __init__(self, bot):
        self.bot = bot
        self.voice_channels = {}  # guild_id: channel_id
        self.leaving_guilds = set()  # guilds where bot is intentionally leaving
        self.task = None

    async def connect(self, channel_id):
        channel = self.bot.get_channel(channel_id)
        if not isinstance(channel, discord.VoiceChannel):
            logger.warning("Invalid voice channel")
            return None

        # reuse existing connection if present
        for vc in self.bot.voice_clients:
            if vc.channel.id == channel_id:
                return vc

        logger.info(f"Connecting to voice channel: {channel.name} ({channel.id})")
        return await channel.connect(reconnect=True)

    async def update_presence(self):
        activity_name = f"Đang ảo discord tại {len(self.voice_channels)} room(s)"
        await self.bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name=activity_name))

    async def burst_loop(self):
        await self.bot.wait_until_ready()

        while not self.bot.is_closed():
            if not self.voice_channels:
                await asyncio.sleep(5)
                continue
            try:
                for guild_id, channel_id in list(self.voice_channels.items()):
                    vc = await self.connect(channel_id)

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
        await self.update_presence()

    @commands.command()
    async def join(self, ctx, channel: discord.VoiceChannel = None):
        if channel is None:
            # If no channel specified, use the author's current voice channel
            if ctx.author.voice and ctx.author.voice.channel:
                channel = ctx.author.voice.channel
            else:
                await ctx.send("Bạn phải ở trong một kênh voice hoặc chỉ định một kênh.")
                return

        self.voice_channels[ctx.guild.id] = channel.id
        vc = await self.connect(channel.id)
        if vc:
            await ctx.send(f"Đã vào {channel.mention}")
            await self.update_presence()
            if self.task is None or self.task.done():
                self.task = asyncio.create_task(self.burst_loop())

    @commands.command()
    async def leave(self, ctx):
        guild_id = ctx.guild.id
        if guild_id not in self.voice_channels:
            await ctx.send("Đang không ở trong room nào cả.")
            return

        channel_id = self.voice_channels[guild_id]

        self.leaving_guilds.add(guild_id)

        # Disconnect from voice
        for vc in self.bot.voice_clients:
            if vc.channel.id == channel_id:
                await vc.disconnect()
                break

        del self.voice_channels[guild_id]
        self.leaving_guilds.remove(guild_id)

        # If no more channels, stop the task
        if not self.voice_channels:
            if self.task and not self.task.done():
                self.task.cancel()
                self.task = None

        await self.update_presence()
        await ctx.send("Đã rời room")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member == self.bot.user and after.channel is None:
            guild_id = before.channel.guild.id if before.channel else None
            if guild_id and guild_id in self.voice_channels and guild_id not in self.leaving_guilds:
                logger.warning("Disconnected from voice, reconnecting...")
                await asyncio.sleep(2)  # small delay helps stability
                await self.connect(self.voice_channels[guild_id])


async def setup(bot):
    await bot.add_cog(Voice(bot))
