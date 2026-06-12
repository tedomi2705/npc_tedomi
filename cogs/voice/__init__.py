import asyncio
import logging
import os

import discord
import redis.asyncio as redis
from discord.ext import commands

from .join import JoinCommand
from .leave import LeaveCommand


logger = logging.getLogger("discord.tedomi.voice")

VOICE_RECONNECT_GRACE_SECONDS = 90
VOICE_RECONCILE_SECONDS = 300
VOICE_CHANNELS_KEY = os.getenv("VOICE_CHANNELS_REDIS_KEY", "npc:voice_channels")


class Voice(JoinCommand, LeaveCommand, commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.voice_channels = {}  # guild_id: channel_id
        self.leaving_guilds = set()  # guilds where bot is intentionally leaving
        self.connect_locks = {}  # guild_id: asyncio.Lock
        self.reconnect_tasks = {}  # guild_id: asyncio.Task
        self.task = None

        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            raise RuntimeError("REDIS_URL environment variable is required")

        self.redis = redis.Redis.from_url(redis_url, decode_responses=True)
        self.voice_channels = {}

    async def initialize(self):
        await self.redis.ping()
        self.voice_channels = await self._load_channel_map()

    async def _load_channel_map(self):
        channels = {}
        try:
            saved_channels = await self.redis.hgetall(VOICE_CHANNELS_KEY)
            for key, value in saved_channels.items():
                try:
                    guild_id = int(key)
                    channel_id = int(value)
                except Exception:
                    continue
                channels[guild_id] = channel_id
        except Exception as e:
            logger.error(f"Failed loading voice channel DB: {e}")
        return channels

    async def _save_channel(self, guild_id, channel_id):
        await self.redis.hset(VOICE_CHANNELS_KEY, str(guild_id), str(channel_id))

    async def _delete_channel(self, guild_id):
        await self.redis.hdel(VOICE_CHANNELS_KEY, str(guild_id))

    def cog_unload(self):
        if self.task and not self.task.done():
            self.task.cancel()
        for task in self.reconnect_tasks.values():
            if not task.done():
                task.cancel()
        asyncio.create_task(self.redis.aclose())

    def _connect_lock(self, guild_id):
        lock = self.connect_locks.get(guild_id)
        if lock is None:
            lock = asyncio.Lock()
            self.connect_locks[guild_id] = lock
        return lock

    def _voice_client_for_guild(self, guild_id):
        for vc in self.bot.voice_clients:
            guild = getattr(vc, "guild", None)
            if guild and guild.id == guild_id:
                return vc

            channel = getattr(vc, "channel", None)
            guild = getattr(channel, "guild", None)
            if guild and guild.id == guild_id:
                return vc
        return None

    def _cancel_reconnect(self, guild_id):
        task = self.reconnect_tasks.pop(guild_id, None)
        if task and task is not asyncio.current_task() and not task.done():
            task.cancel()

    def _schedule_reconnect(self, guild_id, channel_id):
        task = self.reconnect_tasks.get(guild_id)
        if task and not task.done():
            return
        self.reconnect_tasks[guild_id] = asyncio.create_task(
            self.reconnect_after_grace(guild_id, channel_id)
        )

    async def connect(self, channel_id, *, restart_stale=False):
        channel = self.bot.get_channel(channel_id)
        if not isinstance(channel, discord.VoiceChannel):
            logger.warning("Invalid voice channel %s", channel_id)
            return None

        guild_id = channel.guild.id
        async with self._connect_lock(guild_id):
            vc = self._voice_client_for_guild(guild_id)
            if vc:
                current_channel = getattr(vc, "channel", None)
                if vc.is_connected():
                    if current_channel and current_channel.id == channel_id:
                        self._cancel_reconnect(guild_id)
                        return vc

                    logger.info(
                        "Moving voice connection in guild %s to channel %s",
                        guild_id,
                        channel.id,
                    )
                    await vc.move_to(channel)
                    self._cancel_reconnect(guild_id)
                    return vc

                if not restart_stale:
                    logger.info(
                        "Voice client for guild %s is not connected; waiting for "
                        "discord.py reconnect before starting a new handshake.",
                        guild_id,
                    )
                    self._schedule_reconnect(guild_id, channel_id)
                    return vc

                try:
                    await vc.disconnect()
                except Exception:
                    logger.exception(
                        "Error disconnecting stale voice client for guild %s", guild_id
                    )

            logger.info("Connecting to voice channel: %s (%s)", channel.name, channel.id)
            vc = await channel.connect(reconnect=True)
            self._cancel_reconnect(guild_id)
            return vc

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
                    channel = self.bot.get_channel(channel_id)
                    if channel is None:
                        logger.warning(
                            "Voice channel %s not found, removing saved entry for guild %s",
                            channel_id,
                            guild_id,
                        )
                        self.voice_channels.pop(guild_id, None)
                        await self._delete_channel(guild_id)
                        await self.update_presence()
                        continue

                    vc = self._voice_client_for_guild(guild_id)
                    if vc is None or not vc.is_connected():
                        await self.connect(channel_id)

                await asyncio.sleep(VOICE_RECONCILE_SECONDS)

            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Voice loop error")
                await asyncio.sleep(5)

    async def reconnect_after_grace(self, guild_id, channel_id):
        try:
            await asyncio.sleep(VOICE_RECONNECT_GRACE_SECONDS)
            if self.bot.is_closed() or guild_id not in self.voice_channels:
                return

            vc = self._voice_client_for_guild(guild_id)
            if vc and vc.is_connected():
                return

            logger.info(
                "Voice connection for guild %s did not recover after %ss; reconnecting.",
                guild_id,
                VOICE_RECONNECT_GRACE_SECONDS,
            )
            await self.connect(channel_id, restart_stale=True)
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Delayed voice reconnect failed for guild %s", guild_id)
        finally:
            task = self.reconnect_tasks.get(guild_id)
            if task is asyncio.current_task():
                self.reconnect_tasks.pop(guild_id, None)

    @commands.Cog.listener()
    async def on_ready(self):
        await self.update_presence()
        if self.voice_channels and (self.task is None or self.task.done()):
            self.task = asyncio.create_task(self.burst_loop())

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
                    "Bot disconnected from voice in guild %s; letting discord.py "
                    "manage reconnect before scheduling fallback.",
                    guild_id,
                )
                channel_id = self.voice_channels.get(guild_id)
                if channel_id:
                    self._cancel_reconnect(guild_id)
                    self._schedule_reconnect(guild_id, channel_id)
        elif member == self.bot.user and after.channel is not None:
            self._cancel_reconnect(after.channel.guild.id)


async def setup(bot):
    cog = Voice(bot)
    await cog.initialize()
    await bot.add_cog(cog)
