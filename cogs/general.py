import ast
import asyncio
import json
import logging
import math
import operator
import os
import re
import textwrap
import time
import uuid

import discord
import redis.asyncio as redis
from discord.ext import commands


CALC_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

CALC_FUNCTIONS = {
    "sqrt": math.sqrt,
}

MAX_CALC_POWER = 100
MAX_CALC_ABS_RESULT = 10**100
MAX_ALARM_SECONDS = 30 * 24 * 60 * 60
ALARMS_KEY = os.getenv("ALARMS_REDIS_KEY", "npc:alarms")
logger = logging.getLogger("discord.tedomi.general")


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


def calculate_expression(expression: str):
    expression = expression.replace("^", "**")
    tree = ast.parse(expression, mode="eval")

    def eval_node(node):
        if isinstance(node, ast.Expression):
            return eval_node(node.body)

        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value

        if isinstance(node, ast.BinOp) and type(node.op) in CALC_OPERATORS:
            left = eval_node(node.left)
            right = eval_node(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > MAX_CALC_POWER:
                raise ValueError("Số mũ quá lớn.")

            result = CALC_OPERATORS[type(node.op)](left, right)
            if abs(result) > MAX_CALC_ABS_RESULT:
                raise ValueError("Kết quả quá lớn.")
            return result

        if isinstance(node, ast.UnaryOp) and type(node.op) in CALC_OPERATORS:
            return CALC_OPERATORS[type(node.op)](eval_node(node.operand))

        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in CALC_FUNCTIONS
            and len(node.args) == 1
            and not node.keywords
        ):
            return CALC_FUNCTIONS[node.func.id](eval_node(node.args[0]))

        raise ValueError("Biểu thức không hợp lệ.")

    return eval_node(tree)


class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.alarm_tasks = {}
        self.alarms_loaded = False

        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            raise RuntimeError("REDIS_URL environment variable is required")

        self.redis = redis.Redis.from_url(redis_url, decode_responses=True)

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

    @commands.command()
    async def qr(self, ctx, *, choice: str = None):
        if choice is None:
            await ctx.send(
                "https://media.discordapp.net/attachments/1409132849545871420/1499778199079489567/2384DC44-9DA1-4384-ABEE-A4E4B1B20DB9.jpg?ex=69fbf78b&is=69faa60b&hm=ada2abcc848bf7d973fd6d1ef496b79e989f7f49f3e69315fe589014df99598d&=&format=webp&width=860&height=856"
            )
            return
        choice = choice.lower()

        qr_targets = [
            (
                ["meo", "<@575518526811537408>", "<@611533816774787102>"],
                "https://media.discordapp.net/attachments/1409132849545871420/1499778199389737102/att.by7O9FQUF9QDVoMUslJMKMXkA3svgJP3t_D1SOyuDuc.jpg?ex=69fbf78b&is=69faa60b&hm=1db9c29863a841a4b4557fe448229ab18255ae724085a0ffb81effa60086aaf9&=&format=webp&width=481&height=856"
            ),
            (
                ["mi", "<@208174648657969152>"],
                "https://media.discordapp.net/attachments/1133629749672030248/1179353378850095155/Vietcombank_05d89b35-e04a-415f-bce6-6d71942fb6fc.jpg?ex=69f866ec&is=69f7156c&hm=6a2df6f8d4c61b57e3e4e29da88bcf3e6eeeebe33ea6032abe7341953972c469&=&format=webp&width=733&height=960"
            ),
            (
                ["orn", "ỏn", "<@593394674207555584>"],
                "https://media.discordapp.net/attachments/1438873929728131082/1501476416850628668/image.png?ex=69fc3661&is=69fae4e1&hm=1401c4c6413be4321dc0b9fad498cdafa2dc406355d973d78a9e6e1234323a48&=&format=webp&quality=lossless&width=443&height=959"
            ),
        ]

        for keywords, url in qr_targets:
            if any(keyword in choice for keyword in keywords):
                await ctx.send(url)
                return

        await ctx.send('Chỉ hỗ trợ QR của "meo", "mi", hoặc "ỏn".')

    @commands.command()
    async def zypage(self, ctx):
        await ctx.send("https://zypage.com/tedomi")

    @commands.command()
    async def daily(self, ctx):
        messages = f"""
                    {ctx.author.mention}, bạn đã nhận được không gì cả eheheeh
                    chơi `odaily` hay `ndaily` kia kìa
                    """
        await ctx.send(textwrap.dedent(messages).strip())

    @commands.command()
    async def random(self, ctx):
        await ctx.reply("1 bạn ngẫu nhiên: <@208174648657969152>")

    @commands.command()
    async def pick(self, ctx, *, choices: str):
        options = [choice.strip() for choice in choices.split(",") if choice.strip()]
        if not options:
            await ctx.send("Vui lòng cung cấp ít nhất một lựa chọn, phân tách bằng dấu phẩy.")
            return
        import random

        selected = random.choice(options)
        await ctx.send(f"Tôi chọn: {selected}")

    @commands.command()
    async def calc(self, ctx, *, expression: str):
        try:
            result = calculate_expression(expression)
        except ZeroDivisionError:
            await ctx.send("Không thể chia cho 0.")
            return
        except (SyntaxError, ValueError, TypeError, OverflowError):
            await ctx.send("Biểu thức không hợp lệ. Ví dụ: `tcalc (2 + 3) * 4`")
            return

        await ctx.send(f"Kết quả: {result}")

    @commands.command(name="alarm")
    async def alarm(self, ctx, duration: str = None, *, message: str = None):
        if duration is None or message is None or not message.strip():
            await ctx.send("Cú pháp: `talarm [thời gian] [nội dung]`, ví dụ `talarm 3m uống nước`.")
            return

        try:
            seconds = parse_alarm_duration(duration)
        except ValueError:
            await ctx.send("Thời gian hợp lệ: `s`, `m`, `h`, `d`. Ví dụ: `3m`, `6h`, `3h6m`. Tối đa 30 ngày.")
            return

        alarm_id = str(uuid.uuid4())
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
        await ctx.send(f"Đã đặt nhắc sau <t:{int(due_at)}:R>.")
    
    @commands.command()
    async def roll(self, ctx, choices: str):
        numbers = [choice.strip() for choice in choices.split(",") if choice.strip()]
        if len(numbers) != 2:
            await ctx.send("Cú pháp: `troll [số_đầu],[số_cuối]")
            return
        try:
            start, end = map(int, numbers)
        except ValueError:
            await ctx.send("Cú pháp: `troll [số_đầu],[số_cuối]")
            return
        if start >= end:
            await ctx.send("Số đầu phải nhỏ hơn số cuối.")
            return
        import random

        result = random.randint(start, end)
        await ctx.send(f"Bạn đã lắc được: {result}")

async def setup(bot):
    await bot.add_cog(General(bot))
