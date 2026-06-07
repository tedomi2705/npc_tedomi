import asyncio
import json
import logging
import os
import re
import time
import uuid

import discord
from discord.ext import commands


MAX_ALARM_SECONDS = 30 * 24 * 60 * 60
ALARMS_KEY = os.getenv("ALARMS_REDIS_KEY", "npc:alarms")
logger = logging.getLogger("discord.tedomi.general.alarm")
MAX_ALARM_LIST_ITEMS = 20
MAX_ALARM_LIST_MESSAGE_LENGTH = 120


def parse_alarm_duration(duration: str):
    multipliers = {
        "s": 1,
        "m": 60,
        "h": 60 * 60,
        "d": 24 * 60 * 60,
    }

    duration = duration.strip().lower()
    seconds = 0
    position = 0
    for match in re.finditer(r"(\d+)([smhd])", duration):
        if match.start() != position:
            raise ValueError("Thời gian không hợp lệ.")

        value = int(match.group(1))
        unit = match.group(2)
        seconds += value * multipliers[unit]
        position = match.end()

    if position != len(duration):
        raise ValueError("Thời gian không hợp lệ.")

    if seconds <= 0 or seconds > MAX_ALARM_SECONDS:
        raise ValueError("Thời gian không hợp lệ.")
    return seconds


class AlarmCommand:
    def cog_unload(self):
        for task in self.alarm_tasks.values():
            if not task.done():
                task.cancel()
        asyncio.create_task(self.redis.aclose())

    async def _load_alarms(self):
        try:
            saved_alarms = await self.redis.hgetall(ALARMS_KEY)
        except Exception:
            logger.exception("Failed loading alarms from Redis")
            return

        for alarm_id, raw_alarm in saved_alarms.items():
            if alarm_id in self.alarm_tasks:
                continue

            try:
                alarm = json.loads(raw_alarm)
                due_at = float(alarm["due_at"])
                channel_id = int(alarm["channel_id"])
                author_id = int(alarm["author_id"])
                message = str(alarm["message"])
            except Exception:
                logger.warning("Deleting invalid alarm payload: %s", alarm_id)
                await self.redis.hdel(ALARMS_KEY, alarm_id)
                continue

            self._schedule_alarm(alarm_id, due_at, channel_id, author_id, message)

    def _schedule_alarm(self, alarm_id, due_at, channel_id, author_id, message):
        task = asyncio.create_task(
            self._send_alarm(alarm_id, due_at, channel_id, author_id, message)
        )
        self.alarm_tasks[alarm_id] = task

    async def _new_alarm_id(self):
        for _ in range(5):
            alarm_id = uuid.uuid4().hex[:8]
            if not await self.redis.hexists(ALARMS_KEY, alarm_id):
                return alarm_id
        return str(uuid.uuid4())

    async def _unset_alarm(self, ctx, alarm_id):
        alarm_id = alarm_id.strip()
        if not alarm_id:
            await ctx.reply("Cú pháp: `talarm unset [id]`.", mention_author=False)
            return

        raw_alarm = await self.redis.hget(ALARMS_KEY, alarm_id)
        if raw_alarm is None:
            await ctx.reply("Không tìm thấy alarm đó.", mention_author=False)
            return

        try:
            alarm = json.loads(raw_alarm)
            author_id = int(alarm["author_id"])
        except Exception:
            author_id = ctx.author.id

        if author_id != ctx.author.id:
            await ctx.reply("Bạn chỉ có thể huỷ alarm của chính bạn.", mention_author=False)
            return

        await self.redis.hdel(ALARMS_KEY, alarm_id)
        task = self.alarm_tasks.pop(alarm_id, None)
        if task and not task.done():
            task.cancel()

        await ctx.reply(f"Đã huỷ alarm `{alarm_id}`.", mention_author=False)

    async def _list_alarms(self, ctx):
        try:
            saved_alarms = await self.redis.hgetall(ALARMS_KEY)
        except Exception:
            logger.exception("Failed listing alarms from Redis")
            await ctx.reply("Không đọc được danh sách alarm.", mention_author=False)
            return

        alarms = []
        for alarm_id, raw_alarm in saved_alarms.items():
            try:
                alarm = json.loads(raw_alarm)
                author_id = int(alarm["author_id"])
                due_at = float(alarm["due_at"])
                message = str(alarm["message"])
            except Exception:
                logger.warning("Deleting invalid alarm payload: %s", alarm_id)
                await self.redis.hdel(ALARMS_KEY, alarm_id)
                continue

            if author_id != ctx.author.id:
                continue

            alarms.append((due_at, alarm_id, message))

        if not alarms:
            embed = discord.Embed(
                title="Alarm hiện tại của bạn",
                description="Bạn chưa có alarm nào.",
                color=discord.Color.blurple(),
            )
            await ctx.reply(embed=embed, mention_author=False)
            return

        alarms.sort()
        lines = []
        for due_at, alarm_id, message in alarms[:MAX_ALARM_LIST_ITEMS]:
            message = message.replace("`", "'")
            if len(message) > MAX_ALARM_LIST_MESSAGE_LENGTH:
                message = message[: MAX_ALARM_LIST_MESSAGE_LENGTH - 3] + "..."
            lines.append(f"- `{alarm_id}` - <t:{int(due_at)}:R> - {message}")

        if len(alarms) > MAX_ALARM_LIST_ITEMS:
            lines.append(f"- ... và {len(alarms) - MAX_ALARM_LIST_ITEMS} alarm khác.")

        embed = discord.Embed(
            title="Alarm hiện tại của bạn",
            description="\n".join(lines),
            color=discord.Color.blurple(),
        )
        await ctx.reply(embed=embed, mention_author=False)

    async def _send_alarm(self, alarm_id, due_at, channel_id, author_id, message):
        try:
            await asyncio.sleep(max(0, due_at - time.time()))
            channel = self.bot.get_channel(channel_id)
            if channel is None:
                channel = await self.bot.fetch_channel(channel_id)

            await channel.send(f"<@{author_id}> nhắc nè: {message}")
            await self.redis.hdel(ALARMS_KEY, alarm_id)
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Failed sending alarm %s", alarm_id)
            await self.redis.hdel(ALARMS_KEY, alarm_id)
        finally:
            self.alarm_tasks.pop(alarm_id, None)

    @commands.Cog.listener()
    async def on_ready(self):
        if self.alarms_loaded:
            return

        self.alarms_loaded = True
        await self._load_alarms()

    @commands.command(name="alarm")
    async def alarm(self, ctx, duration: str = None, *, message: str = None):
        if duration is None:
            await ctx.reply(
                "Cú pháp: `talarm [thời gian] [nội dung]`, ví dụ `talarm 3m uống nước`."
                "\nXem alarm: `talarm list`."
                "\nHuỷ alarm: `talarm unset [id]`.",
                mention_author=False,
            )
            return

        if duration.lower() == "list":
            await self._list_alarms(ctx)
            return

        if duration.lower() == "unset":
            if message is None:
                await ctx.reply("Cú pháp: `talarm unset [id]`.", mention_author=False)
                return
            await self._unset_alarm(ctx, message)
            return

        if message is None or not message.strip():
            await ctx.reply(
                "Cú pháp: `talarm [thời gian] [nội dung]`, ví dụ `talarm 3m uống nước`.",
                mention_author=False,
            )
            return

        try:
            seconds = parse_alarm_duration(duration)
        except ValueError:
            await ctx.reply(
                "Thời gian hợp lệ: `s`, `m`, `h`, `d`. Ví dụ: `3m`, `6h`, `3h6m`. Tối đa 30 ngày.",
                mention_author=False,
            )
            return

        alarm_id = await self._new_alarm_id()
        due_at = time.time() + seconds
        message = message.strip()
        alarm = {
            "due_at": due_at,
            "channel_id": ctx.channel.id,
            "author_id": ctx.author.id,
            "message": message,
        }
        await self.redis.hset(ALARMS_KEY, alarm_id, json.dumps(alarm))
        self._schedule_alarm(alarm_id, due_at, ctx.channel.id, ctx.author.id, message)
        await ctx.reply(
            f"Đã đặt nhắc sau <t:{int(due_at)}:R>. ID: `{alarm_id}`. Huỷ bằng `talarm unset {alarm_id}`.",
            mention_author=False,
        )
