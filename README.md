# NPC Bot

Run the bot using UV from the project root:

```bash
uv run main.py
```

The Dockerfile is already configured to use UV as the entrypoint.

Configure these environment variables in `.env`:

```bash
TOKEN=your-discord-bot-token
REDIS_URL=rediss://default:your-upstash-password@your-upstash-host:6379
```

## Availability

The container exposes an internal HTTP healthcheck on `HEALTH_PORT` (`8080` by default). Docker marks the container healthy only after the Discord gateway is ready. If the bot stays unready for `HEALTH_UNREADY_EXIT_SECONDS` (`300` by default), it exits so `docker-compose.yml` can restart it automatically.

Run with Docker Compose:

```bash
docker compose up -d --build
```

Voice channel state is stored in Upstash Redis using `VOICE_CHANNELS_REDIS_KEY` (`npc:voice_channels` by default), so failover does not depend on a local Docker volume.
Pending `talarm` reminders are stored in the same Redis instance using `ALARMS_REDIS_KEY` (`npc:alarms` by default), so reminders survive bot restarts.

Discord bots using one token should not run active-active replicas. For failover across hosts, run one active container at a time and let your orchestrator start a replacement on another host using the same Upstash Redis instance.
