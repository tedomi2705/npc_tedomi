import textwrap

from discord.ext import commands


class DailyCommand:
    @commands.command()
    async def daily(self, ctx):
        messages = f"""
                    {ctx.author.mention}, bạn đã nhận được không gì cả eheheeh
                    chơi `odaily` hay `ndaily` kia kìa
                    """
        await ctx.reply(textwrap.dedent(messages).strip(), mention_author=False)
