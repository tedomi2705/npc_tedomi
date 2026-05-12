import asyncio
import logging
from pathlib import Path

import discord
import plyvel
from discord.ext import commands

logger = logging.getLogger("discord.tedomi.voice")


class Voice(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.voice_channels = {}  # guild_id: channel_id
        self.leaving_guilds = set()  # guilds where bot is intentionally leaving
        self.task = None

        self.db_path = Path(__file__).resolve().parents[1] / "data" / "voice_channels"
        self.db_path.mkdir(parents=True, exist_ok=True)
        self.db = plyvel.DB(self.db_path.as_posix(), create_if_missing=True)
        self.voice_channels = self._load_channel_map()

    def _load_channel_map(self):
        channels = {}
        try:
            for key, value in self.db:
                try:
                    guild_id = int(key.decode("utf-8"))
                    channel_id = int(value.decode("utf-8"))
                except Exception:
                    continue
                channels[guild_id] = channel_id
        except Exception as e:
            logger.error(f"Failed loading voice channel DB: {e}")
        return channels

    def _save_channel(self, guild_id, channel_id):
        self.db.put(str(guild_id).encode(), str(channel_id).encode())

    def _delete_channel(self, guild_id):
        self.db.delete(str(guild_id).encode())

    def cog_unload(self):
        if self.task and not self.task.done():
            self.task.cancel()
        self.db.close()

    async def connect(self, channel_id):
        channel = self.bot.get_channel(channel_id)
        if not isinstance(channel, discord.VoiceChannel):
            logger.warning("Invalid voice channel")
            return None

        # reuse existing connection if present
        for vc in self.bot.voice_clients:
            if vc.channel.id == channel_id:
                if vc.is_connected():
                    return vc
                try:
                    await vc.disconnect()
                except Exception as e:
                    logger.warning(f"Error disconnecting existing voice client: {e}")
                break

        logger.info(f"Connecting to voice channel: {channel.name} ({channel.id})")
        return await channel.connect(reconnect=True)

    async def update_presence(self):
        activity_name = f"Đang ảo discord tại {len(self.voice_channels)} room(s)"
        await self.bot.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.listening, name=activity_name
            )
        )

    async def burst_loop(self):
        await self.bot.wait_until_ready()

        while not self.bot.is_closed():
            if not self.voice_channels:
                await asyncio.sleep(5)
                continue
            try:
                for guild_id, channel_id in list(self.voice_channels.items()):
                    vc = await self.connect(channel_id)

                    if vc is None:
                        if not self.bot.get_channel(channel_id):
                            logger.warning(
                                "Voice channel %s not found, removing saved entry for guild %s",
                                channel_id,
                                guild_id,
                            )
                            self.voice_channels.pop(guild_id, None)
                            self._delete_channel(guild_id)
                            await self.update_presence()
                        continue

                await asyncio.sleep(36)

            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Voice loop error")
                await asyncio.sleep(5)

    @commands.Cog.listener()
    async def on_ready(self):
        await self.update_presence()
        if self.voice_channels and (self.task is None or self.task.done()):
            self.task = asyncio.create_task(self.burst_loop())

    @commands.command()
    async def join(self, ctx, channel: discord.VoiceChannel = None):
        if channel is None:
            # If no channel specified, use the author's current voice channel
            if ctx.author.voice and ctx.author.voice.channel:
                channel = ctx.author.voice.channel
            else:
                await ctx.send(
                    "Bạn phải ở trong một kênh voice hoặc chỉ định một kênh."
                )
                return

        self.voice_channels[ctx.guild.id] = channel.id
        self._save_channel(ctx.guild.id, channel.id)
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
        self._delete_channel(guild_id)
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
            if guild_id and guild_id in self.leaving_guilds:
                logger.info(
                    "Bot intentionally left voice in guild %s, no reconnect.", guild_id
                )
            else:
                logger.info(
                    "Bot disconnected from voice in guild %s; letting discord.py manage reconnect.",
                    guild_id,
                )


async def setup(bot):
    await bot.add_cog(Voice(bot))
