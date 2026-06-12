from discord.ext import commands


class LietCommand:
    @commands.command()
    async def liet(self, ctx):
        await ctx.reply("<:TLiet:1433781478847807620>", mention_author=False)
