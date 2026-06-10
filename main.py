import asyncio
import logging
import os
from dotenv import load_dotenv

import discord
from discord.ext import commands

load_dotenv()
TOKEN = os.getenv("TOKEN")
HEALTH_HOST = os.getenv("HEALTH_HOST", "0.0.0.0")
HEALTH_PORT = int(os.getenv("HEALTH_PORT", "8080"))
HEALTH_UNREADY_EXIT_SECONDS = int(os.getenv("HEALTH_UNREADY_EXIT_SECONDS", "300"))
LOG_LEVEL = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)
logger = logging.getLogger("discord")

intents = discord.Intents.default()
intents.message_content = True


class NPCBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix=("t", "T"),
            case_insensitive=True,
            strip_after_prefix=True,
            intents=intents,
        )
        self.health_server = None
        self.health_watchdog_task = None

    async def setup_hook(self):
        await self.load_extension("cogs.general")
        await self.load_extension("cogs.voice")
        self.health_server = await asyncio.start_server(
            self.handle_healthcheck, HEALTH_HOST, HEALTH_PORT
        )
        self.health_watchdog_task = asyncio.create_task(self.watch_health())
        logger.info("Healthcheck listening on %s:%s", HEALTH_HOST, HEALTH_PORT)

    async def close(self):
        if (
            self.health_watchdog_task
            and self.health_watchdog_task is not asyncio.current_task()
        ):
            self.health_watchdog_task.cancel()
        if self.health_server:
            self.health_server.close()
            await self.health_server.wait_closed()

        for voice_client in list(self.voice_clients):
            try:
                await voice_client.disconnect(force=True)
            except Exception:
                logger.exception("Error disconnecting voice client during shutdown")

        await super().close()

    async def watch_health(self):
        loop = asyncio.get_running_loop()
        unready_since = loop.time()

        while not self.is_closed():
            if self.is_ready():
                unready_since = loop.time()
            elif loop.time() - unready_since >= HEALTH_UNREADY_EXIT_SECONDS:
                logger.error(
                    "Bot has been unready for %ss; exiting for supervisor restart",
                    HEALTH_UNREADY_EXIT_SECONDS,
                )
                await self.close()
                return

            await asyncio.sleep(10)

    async def handle_healthcheck(self, reader, writer):
        try:
            await reader.read(1024)
            healthy = self.is_ready() and not self.is_closed()
            status = "200 OK" if healthy else "503 Service Unavailable"
            body = b"ok\n" if healthy else b"not ready\n"
            writer.write(
                b"HTTP/1.1 "
                + status.encode("ascii")
                + b"\r\nContent-Type: text/plain\r\nContent-Length: "
                + str(len(body)).encode("ascii")
                + b"\r\nConnection: close\r\n\r\n"
                + body
            )
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()


bot = NPCBot()


# Use uv to run this bot:
#   uv run main.py
if __name__ == "__main__":
    if not TOKEN:
        raise RuntimeError("TOKEN environment variable is required")

    bot.run(TOKEN, log_level=LOG_LEVEL)
