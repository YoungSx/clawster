# OpenClaw Distributed Skill

Distributed cluster coordination skill supporting multi-node leader election, heartbeat monitoring, and task distribution via Redis.

## Table of Contents
- [Quick Start](#quick-start)
- [Core Components](#core-components)
- [Redis Schema](#redis-schema)
- [Heartbeat Mechanism](#heartbeat-mechanism)
- [FAQ](#faq)

## Directory Structure

```
.
├── README.md          # This file (Chinese)
├── README_EN.md       # English documentation
├── SKILL.md           # OpenClaw skill metadata
├── requirements.txt   # Python dependencies (empty, stdlib only)
├── start-node.sh      # Node startup script
├── config/            # Configuration directory
│   ├── config.json    # General config (node ID, intervals)
│   └── secrets.json   # Sensitive info (Redis password) - gitignore
├── scripts/           # Core scripts
│   ├── heartbeat.py       # Heartbeat script (cron scheduled)
│   ├── redis_client.py    # Pure Python Redis client (RESP)
│   ├── node_manager.py    # Node lifecycle management
│   ├── leader_election.py # Leader election logic
│   ├── failover_manager.py# Failover handling
│   └── state_sync.py      # State synchronization
└── logs/              # Log directory
    └── heartbeat.log  # Rotated logs (10MB)
```

## Quick Start

### 1. Configure Redis Connection

**Option 1: Config file (recommended)**
Edit `config/secrets.json` (gitignored):

```json
{
  "redis": {
    "host": "your-redis-host",
    "port": 11877,
    "password": "your-password",
    "db": 0
  }
}
```

**Option 2: Environment variables** (higher priority)

```bash
export REDIS_HOST=your-redis-host
export REDIS_PORT=11877
export REDIS_PASSWORD=your-password
export REDIS_DB=0
export OPENCLAW_NODE_ID=main-node
```

### 2. Configure Node Parameters

Edit `config/config.json`:

```json
{
  "node": {
    "id": "main-node",
    "heartbeat_interval": 10,
    "heartbeat_ttl": 30,
    "retry_count": 3,
    "retry_delay": 1
  },
  "logging": {
    "level": "INFO",
    "max_bytes": 10485760,
    "backup_count": 5
  }
}
```

### 3. Start Heartbeat (via OpenClaw Cron)

```bash
openclaw cron add \
  --name "distributed-node-heartbeat" \
  --every 10s \
  --system-event "EXEC: ./scripts/heartbeat.py" \
  --agent main
```

### 4. Verify Heartbeat

```bash
# List cron jobs
openclaw cron list

# View logs
tail -f logs/heartbeat.log
```

## Core Components

### heartbeat.py
Cron-scheduled node heartbeat script:
- Sends heartbeat every 10s (configurable)
- Auto-retry on failure (3 attempts)
- Multi-channel logging: file + console + syslog

**Manual test:**
```bash
python3 scripts/heartbeat.py
```

### redis_client.py
Pure Python Redis client, zero external dependencies:
- RESP protocol via standard `socket` library
- Commands: HSET, HGET, SETEX, GET, DELETE
- Connection pooling with 5s timeout

### node_manager.py
Node lifecycle management:
- Registration / deregistration
- Health checks
- Status detection

### leader_election.py
Leader election with Redis RedLock algorithm:
- Automatic failover
- Lease renewal

## Redis Schema

| Key | Type | Description |
|-----|------|-------------|
| `openclaw:cluster:nodes` | Hash | All node info (field: node_id, value: JSON) |
| `hb:{node_id}` | String | Node heartbeat TTL (30s expiry) |
| `openclaw:cluster:leader` | String | Current leader node ID |

## Heartbeat Mechanism

```
┌──────────┐  every 10s  ┌─────────┐  ┌─────────┐
│ Cron Job │ ───────────▶ │ Script  │──▶│  Redis  │
└──────────┘             └─────────┘  └─────────┘
     │                        │             │
     ▼                        ▼             ▼
        logs/heartbeat.log       TTL=30s (rotated 10MB)
```

**Failure Recovery:**
- Auto-retry 3 times on failure
- Node marked offline after 30s (3 missed heartbeats)
- Re-election triggered when leader is lost

## FAQ

### Q: Heartbeat script fails?

1. Check Redis config (`config/secrets.json` or env vars)
2. Verify network connectivity to Redis
3. Check logs: `logs/heartbeat.log`

### Q: How to change heartbeat frequency?

1. Update `heartbeat_interval` in `config/config.json`
2. Delete old cron job: `openclaw cron delete <job-id>`
3. Create new job with updated `--every` parameter

### Q: Multi-node configuration?

Set unique `OPENCLAW_NODE_ID` for each node:

```bash
export OPENCLAW_NODE_ID=node-002
```

## Requirements

- Python 3.9+
- Redis 5.0+ (Streams support)
- **Zero pip dependencies** (pure standard library)

## Security Notes

- `config/secrets.json` is gitignored
- Use environment variables in production
- Rotate Redis passwords regularly

## Related Documentation

- [SKILL.md](./SKILL.md) - Full OpenClaw skill specification
- `/app/docs/` - OpenClaw official documentation
