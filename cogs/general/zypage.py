from discord.ext import commands


class ZypageCommand:
    @commands.command()
    async def zypage(self, ctx):
        await ctx.reply("https://zypage.com/tedomi", mention_author=False)
