from discord.ext import commands


class QrCommand:
    @commands.command()
    async def qr(
        self,
        ctx,
        *,
        choice: str = commands.parameter(
            default=None,
            description='Tên/người cần lấy QR, ví dụ: "meo", "mi", hoặc "ỏn".',
        ),
    ):
        if choice is None:
            await ctx.reply(
                "https://media.discordapp.net/attachments/1397095003976761364/1518567885310660678/43CBC1EC-D248-4891-85BA-471846BD3F7C.png?ex=6a3a640d&is=6a39128d&hm=058164fbfd37d160e882e7d07503060d3375a337d57685e9724a22bd77a85893&=&format=webp&quality=lossless&width=640&height=960",
                mention_author=False,
            )
            return
        choice = choice.lower()

        qr_targets = [
            (
                ["meo", "<@575518526811537408>", "<@611533816774787102>"],
                "https://media.discordapp.net/attachments/1409132849545871420/1499778199079489567/2384DC44-9DA1-4384-ABEE-A4E4B1B20DB9.jpg?ex=69fbf78b&is=69faa60b&hm=ada2abcc848bf7d973fd6d1ef496b79e989f7f49f3e69315fe589014df99598d&=&format=webp&width=860&height=856",
            ),
            (
                ["mi", "<@208174648657969152>"],
                "https://media.discordapp.net/attachments/1133629749672030248/1179353378850095155/Vietcombank_05d89b35-e04a-415f-bce6-6d71942fb6fc.jpg?ex=69f866ec&is=69f7156c&hm=6a2df6f8d4c61b57e3e4e29da88bcf3e6eeeebe33ea6032abe7341953972c469&=&format=webp&width=733&height=960",
            ),
            (
                ["orn", "ỏn", "<@593394674207555584>"],
                "https://media.discordapp.net/attachments/1438873929728131082/1501476416850628668/image.png?ex=69fc3661&is=69fae4e1&hm=1401c4c6413be4321dc0b9fad498cdafa2dc406355d973d78a9e6e1234323a48&=&format=webp&quality=lossless&width=443&height=959",
            ),
            (
                ["già", "<@315750883826728961>"],
                "https://cdn.discordapp.com/attachments/1435001187505275034/1515402370509570198/2c88d782-29b0-4e80-8865-9633e751082f.png?ex=6a2f88af&is=6a2e372f&hm=174e521e18c7edbcabd48feedc8004f61ab67571ad31efca28aabef1a3969c4e&",
            ),
        ]

        for keywords, url in qr_targets:
            if any(keyword in choice for keyword in keywords):
                await ctx.reply(url, mention_author=False)
                return

        await ctx.reply('Chỉ hỗ trợ QR của "meo", "mi", "già", hoặc "ỏn".', mention_author=False)
