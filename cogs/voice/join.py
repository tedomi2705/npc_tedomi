import asyncio

import discord
from discord.ext import commands


class JoinCommand:
    @commands.command()
    async def join(
        self,
        ctx,
        channel: discord.VoiceChannel = commands.parameter(
            default=None,
            description="Kênh voice muốn bot tham gia; bỏ trống để dùng kênh hiện tại.",
        ),
    ):
        if channel is None:
            if ctx.author.voice and ctx.author.voice.channel:
                channel = ctx.author.voice.channel
            else:
                await ctx.reply(
                    "Bạn phải ở trong một kênh voice hoặc chỉ định một kênh.",
                    mention_author=False,
                )
                return

        self.voice_channels[ctx.guild.id] = channel.id
        await self._save_channel(ctx.guild.id, channel.id)
        self._cancel_reconnect(ctx.guild.id)
        vc = await self.connect(channel.id)
        if vc:
            await ctx.reply(f"Đã vào {channel.mention}", mention_author=False)
            await self.update_presence()
            if self.task is None or self.task.done():
                self.task = asyncio.create_task(self.burst_loop())
