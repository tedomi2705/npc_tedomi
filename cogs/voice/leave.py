from discord.ext import commands


class LeaveCommand:
    @commands.command()
    async def leave(self, ctx):
        guild_id = ctx.guild.id
        if guild_id not in self.voice_channels:
            await ctx.reply("Đang không ở trong room nào cả.", mention_author=False)
            return

        channel_id = self.voice_channels[guild_id]

        self.leaving_guilds.add(guild_id)

        for vc in self.bot.voice_clients:
            if vc.channel.id == channel_id:
                await vc.disconnect()
                break

        del self.voice_channels[guild_id]
        await self._delete_channel(guild_id)
        self.leaving_guilds.remove(guild_id)

        if not self.voice_channels:
            if self.task and not self.task.done():
                self.task.cancel()
                self.task = None
        self._cancel_reconnect(guild_id)

        await self.update_presence()
        await ctx.reply("Đã rời room", mention_author=False)
