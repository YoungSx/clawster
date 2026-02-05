---
name: clawster
description: Distributed clustering support for OpenClaw. Enables multiple nodes to coordinate via Redis for leader election, heartbeat monitoring, and task distribution. Use when setting up multi-node OpenClaw deployments, configuring high availability, or managing cluster topology.
---

# OpenClaw Distributed Skill

## Overview

Provides distributed clustering capabilities for OpenClaw, enabling multiple nodes to coordinate and share workloads via Redis.

## Installation

```bash
# Install skill
cd skills/clawster
pip install -r requirements.txt

# Make scripts executable
chmod +x start-node.sh
chmod +x scripts/heartbeat.py
```

## Configuration

### 1. 隐私解耦配置

敏感信息（Redis 密码等）已从代码中分离，支持两种方式：

#### 方式一：配置文件（默认）

```
config/
├── config.json      # 通用配置（节点ID、重试次数等）
└── secrets.json     # 敏感信息（Redis 密码等）- .gitignore 已排除
```

**config/config.json**:
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

**config/secrets.json**:
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

#### 方式二：环境变量（优先级更高）

```bash
export REDIS_HOST=your-redis-host
export REDIS_PORT=11877
export REDIS_PASSWORD=your-password
export REDIS_DB=0
export OPENCLAW_NODE_ID=main-node
```

**优先级**: 环境变量 > secrets.json > 默认值

### 2. 旧版配置（已废弃）

旧版 `config.json` 格式：
```json
{
  "cluster": {
    "enabled": true,
    "node_id": "node-001",
    "node_name": "openclaw-node-001",
    "redis": {
      "host": "localhost",
      "port": 6379,
      "password": null,
      "db": 0
    },
    "heartbeat": {
      "interval_ms": 5000,
      "timeout_ms": 15000
    },
    "election": {
      "timeout_ms": 10000,
      "renewal_interval_ms": 5000
    },
    "sync": {
      "batch_size": 100,
      "max_stream_length": 10000
    }
  }
}
```

## OpenClaw Cron 心跳调度

### 创建心跳 Cron Job

OpenClaw 内置的 cron 调度系统用于执行分布式节点心跳（推荐用于 K8s 容器环境）：

```bash
# 创建每10秒执行的心跳任务
openclaw cron add --name "distributed-node-heartbeat" \
  --every 10s \
  --system-event "EXEC: ~/clawd/skills/clawster/scripts/heartbeat.py" \
  --agent main
```

**参数说明：**
| 参数 | 是否必填 | 说明 |
|------|---------|------|
| `--name` | ✅ | Job 名称，用于识别和管理 |
| `--every` | ✅ | 执行间隔，支持秒级（如 `10s`、`1m`、`1h`） |
| `--system-event` | ✅ | 触发的事件类型，`EXEC:` 前缀表示执行命令 |
| `--agent` | ✅ | 执行会话，通常是 `main` |
| `--message` | 二选一 | 派发到 agent 的消息（与 `--system-event` 互斥） |
| `--at` | 可选 | 指定执行时间（如 `2026-02-02T10:00:00Z`） |
| `--cron` | 可选 | Cron 表达式（如 `"0 */6 * * *"`） |

### 查看与管理 Cron Jobs

```bash
# 列出所有 jobs
openclaw cron list

# 查看详情（JSON 格式）
openclaw cron list --json

# 删除 job
openclaw cron delete <job-id>

# 立即执行一次（调试用）
openclaw cron run <job-id>
```

### Cron Job 示例配置

```json
{
  "id": "dc046007-cb6a-40cd-bc97-ab9f7bedf8d3",
  "agentId": "main",
  "name": "distributed-node-heartbeat",
  "enabled": true,
  "schedule": {
    "kind": "every",
    "everyMs": 10000
  },
  "sessionTarget": "main",
  "wakeMode": "next-heartbeat",
  "payload": {
    "kind": "systemEvent",
    "text": "EXEC: ~/clawd/skills/clawster/scripts/heartbeat.py"
  },
  "state": {
    "nextRunAtMs": 1770029598901,
    "lastRunAtMs": 1770029588901,
    "lastStatus": "ok"
  }
}
```

### Cron vs Systemd 对比

| 维度 | OpenClaw Cron | Systemd | 系统 Cron |
|------|---------------|---------|----------|
| 权限需求 | ✅ 无需 root | ❌ 需要特权 | ❌ 需要 root |
| 精度 | ✅ 支持秒级 | ❌ 最低分钟级 | ❌ 最低分钟级 |
| 容器支持 | ✅ K8s 内可用 | ❌ 需 systemd | ⚠️ 需挂载 crontab |
| 分布式执行 | ✅ 跨节点调度 | ❌ 仅本机 | ❌ 仅本机 |
| 日志可观测 | ✅ 统一查看 | ⚠️ journalctl | ⚠️ 分散 |
| 依赖 | OpenClaw Gateway | systemd | cron daemon |

**当前环境**: OpenClaw Cron（K8s 容器，无 systemd 权限）

## 心跳日志

心跳脚本配置双向日志：

- **系统日志**: `/dev/log` (tag: `clawster`)
- **本地文件**: `logs/heartbeat.log` (轮转，10MB)
- **控制台**: stdout（便于调试）

查看日志：
```bash
# 本地日志
tail -f ~/clawd/skills/clawster/logs/heartbeat.log

# 系统日志（如可用）
journalctl -t clawster -f
```

## 心跳重试机制

脚本内置失败重试：

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `retry_count` | 3 | 最大重试次数 |
| `retry_delay` | 1秒 | 重试间隔 |

失败时日志输出：
```
WARNING: 心跳失败 (attempt 1): <错误>，1秒后重试...
ERROR: 心跳失败，已达最大重试次数 3: <错误>
```

## Commands

### Start a Node
```bash
./start-node.sh [NODE_ID] [CONFIG_PATH]
```

### Check Cluster Status
```bash
openclaw distributed status
```

### List Active Nodes
```bash
openclaw distributed nodes
```

### Trigger Leader Election
```bash
openclaw distributed elect
```

## OpenClaw Integration

### Tools Provided

- `distributed.sync_messages()` - Sync messages across cluster
- `distributed.get_cluster_state()` - Get current cluster topology
- `distributed.elect_leader()` - Trigger leader election
- `distributed.join_cluster(node_id)` - Join cluster as new node
- `distributed.leave_cluster()` - Gracefully leave cluster

### Events

The skill emits these events:
- `cluster.node_joined` - A new node joined the cluster
- `cluster.node_left` - A node left the cluster
- `cluster.leader_elected` - New leader elected
- `cluster.sync_complete` - Message sync completed

### Example Usage

```python
# From an OpenClaw agent
async def handle_message(msg):
    # Sync to cluster
    await distributed.sync_messages([msg])
    
    # Check if this node is leader
    state = await distributed.get_cluster_state()
    if state.leader_id == config.node_id:
        # Do leader-only tasks
        pass
```

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Node 1    │◄───►│    Redis    │◄───►│   Node 2    │
│  (Leader)   │     │   Backend   │     │ (Follower)  │
└─────────────┘     └─────────────┘     └─────────────┘
       ▲                                         ▲
       └─────────────────────────────────────────┘
                    (gossip protocol)
```

## Health Checks

Nodes perform automatic health checks:
1. **Heartbeat**: Every 10s (configurable via `config/config.json`)
2. **Leader lease**: Renewed every 10s by leader
3. **Sync**: Batch sync every heartbeat interval

If a node misses 3 heartbeats, it's marked offline.

## Dependencies

- Redis 5.0+ (for Streams and clustering features)
- Python 3.9+

**纯 Python 实现**（无 pip 依赖）：
- 自研 `redis_client.py` 实现 RESP 协议
- 使用标准库：`socket`, `logging`, `json`

## Development

### Running Tests
```bash
cd skills/clawster
python -m pytest tests/
```

### Test Heartbeat Script
```bash
# 单测执行
python3 scripts/heartbeat.py

# 查看输出
tail -f logs/heartbeat.log
```

### Adding New Commands
1. Add command handler in `scripts/commands.py`
2. Register in `SKILL.md`
3. Update `README.md` with usage

## MongoDB Integration

MongoDB 用于记录心跳历史：

- host: `mainline.proxy.rlwy.net`
- port: `59673`
- db: `openclaw`
- collection: `heartbeat`