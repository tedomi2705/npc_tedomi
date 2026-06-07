import os

import redis.asyncio as redis
from discord.ext import commands

from .alarm import AlarmCommand
from .calc import CalcCommand
from .daily import DailyCommand
from .pick import PickCommand
from .qr import QrCommand
from .random import RandomCommand
from .roll import RollCommand
from .zypage import ZypageCommand


class General(
    AlarmCommand,
    CalcCommand,
    DailyCommand,
    PickCommand,
    QrCommand,
    RandomCommand,
    RollCommand,
    ZypageCommand,
    commands.Cog,
):
    def __init__(self, bot):
        self.bot = bot
        self.alarm_tasks = {}
        self.alarms_loaded = False

        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            raise RuntimeError("REDIS_URL environment variable is required")

        self.redis = redis.Redis.from_url(redis_url, decode_responses=True)


async def setup(bot):
    await bot.add_cog(General(bot))
