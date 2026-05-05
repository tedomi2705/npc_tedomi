import discord
from discord.ext import commands
import textwrap

class General(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def qr(self, ctx, choice: str = None):
        if choice is None:
            await ctx.send('https://media.discordapp.net/attachments/1499409101153636494/1499765676192039133/2384DC44-9DA1-4384-ABEE-A4E4B1B20DB9.jpg?ex=69f8a021&is=69f74ea1&hm=dac2b7b18186673af7fd7e9498f54a893b7c9b138040ddd6ef530d9f76a15a90&=&format=webp&width=964&height=960')
            return
        choice = choice.lower()
        if 'mi' in choice:
            await ctx.send('https://media.discordapp.net/attachments/1133629749672030248/1179353378850095155/Vietcombank_05d89b35-e04a-415f-bce6-6d71942fb6fc.jpg?ex=69f866ec&is=69f7156c&hm=6a2df6f8d4c61b57e3e4e29da88bcf3e6eeeebe33ea6032abe7341953972c469&=&format=webp&width=733&height=960')
        elif 'orn' in choice or 'ỏn' in choice:
            await ctx.send('https://media.discordapp.net/attachments/1499409101153636494/1499409183588745318/671719351_2315840635604407_5422268897948339640_n.png?ex=69f8a59f&is=69f7541f&hm=5fc9d315660a6c84ca6afe1f57171731c396a62983facc37cdf4bc19e488d422&=&format=webp&quality=lossless&width=443&height=959')
        elif 'meo' in choice:
            await ctx.send('https://media.discordapp.net/attachments/1499409101153636494/1499409389847707738/image.png?ex=69f8a5d0&is=69f75450&hm=500e537bbfcbbc8a9d8b9e02760ac5ff3e04e523e1f19046b2b26d2b795a144a&=&format=webp&quality=lossless&width=540&height=960')
        else:
            await ctx.send('Chỉ hỗ trợ QR của "meo", "mi", hoặc "ỏn".')

    @commands.command()
    async def zypage(self, ctx):
        await ctx.send('https://zypage.com/tedomi')

    @commands.command()
    async def daily(self, ctx):
        messages = f"""
                    {ctx.author.mention}, bạn đã nhận được không gì cả eheheeh
                    chơi `odaily` hay `ndaily` kia kìa
                    """
        await ctx.send(textwrap.dedent(messages).strip())

async def setup(bot):
    await bot.add_cog(General(bot))