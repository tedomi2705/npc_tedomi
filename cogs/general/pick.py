import random

from discord.ext import commands


class PickCommand:
    @commands.command()
    async def pick(self, ctx, *, choices: str):
        options = [choice.strip() for choice in choices.split(",") if choice.strip()]
        if not options:
            await ctx.reply(
                "Vui lòng cung cấp ít nhất một lựa chọn, phân tách bằng dấu phẩy.",
                mention_author=False,
            )
            return

        selected = random.choice(options)
        await ctx.reply(f"Tôi chọn: {selected}", mention_author=False)
