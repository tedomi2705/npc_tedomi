import random

from discord.ext import commands


class RollCommand:
    @commands.command()
    async def roll(
        self,
        ctx,
        choices: str = commands.parameter(
            description="Khoảng số dạng số_đầu,số_cuối. Ví dụ: 1,100."
        ),
    ):
        numbers = [choice.strip() for choice in choices.split(",") if choice.strip()]
        if len(numbers) != 2:
            await ctx.reply("Cú pháp: `troll [số_đầu],[số_cuối]", mention_author=False)
            return
        try:
            start, end = map(int, numbers)
        except ValueError:
            await ctx.reply("Cú pháp: `troll [số_đầu],[số_cuối]", mention_author=False)
            return
        if start >= end:
            await ctx.reply("Số đầu phải nhỏ hơn số cuối.", mention_author=False)
            return

        result = random.randint(start, end)
        await ctx.reply(f"Bạn đã lắc được: {result}", mention_author=False)
