from discord.ext import commands


class RandomCommand:
    @commands.command()
    async def random(self, ctx):
        await ctx.reply("1 bạn ngẫu nhiên: <@208174648657969152>", mention_author=False)
