# OpenClaw Distributed Skill - Clawster

分布式集群协调技能，支持多节点通过 Redis 进行 leader 选举、心跳监控和任务分发。

**当前版本：** 已实现动态节点发现、Leader选举、自动故障转移

## 核心特性

- **Leader选举**：基于Redis RedLock算法，自动竞选与续约
- **心跳监控**：每10秒心跳，支持自动重试和过期检测
- **节点通信**：通过Redis频道进行消息交换，支持任务提议
- **动态发现**：无需硬编码节点名，从注册表自动发现伙伴
- **一键部署**：提供 joining scripts 快速加入集群

## 目录结构

```
.
├── README.md              # 本文件
├── SKILL.md               # OpenClaw 技能元数据
├── requirements.txt       # Python 依赖（当前为空，使用纯标准库）
├── start-node.sh          # 节点启动脚本
│
├── config/                # 配置文件目录
│   ├── config.json        # 通用配置（节点ID、心跳间隔等）
│   └── secrets.json       # 敏感信息（Redis 密码、OKX API）- gitignore 排除
│
├── scripts/               # 核心脚本
│   ├── heartbeat.py       # 心跳脚本（由 cron 调度执行）
│   ├── redis_client.py    # 纯 Python Redis 客户端（RESP 协议）
│   ├── node_manager.py    # 节点管理
│   ├── leader_election.py # Leader 选举逻辑
│   ├── failover_manager.py# 故障转移
│   └── state_sync.py      # 状态同步          
│
└── logs/                  # 日志目录
    └── heartbeat.log      # 心跳日志（轮转，10MB）
```

## 设置方法详解

本项目使用 **OpenClaw Cron** 进行任务调度，而非系统 crontab。

### OpenClaw Cron 工作原理

| 特征 | OpenClaw Cron | 系统 Cron |
|------|---------------|-----------|
| 配置工具 | `cron` 命令 | `crontab -e` |
| Job ID | 自动生成 UUID | 无 |
| 调度格式 | `{"kind": "every", "everyMs": 10000}` | `*/1 * * * *` |
| 执行方式 | `systemEvent` 触发 | 直接 shell |
| 日志 | `System: [timestamp] EXEC: ...` | 无 |
| 作用域 | OpenClaw 内部 | 系统级别 |

### 创建 Cron Job

**心跳任务**（每10秒）：
```bash
# 查看现有 cron jobs
cron list

# 创建心跳任务
cron add \
  --name "distributed-node-heartbeat" \
  --schedule '{"kind": "every", "everyMs": 10000}' \
  --system-event "EXEC: ~/clawd/clawster/scripts/heartbeat.py" \
  --agent main

# 验证
python3 scripts/heartbeat.py
```

**Leader选举任务**（每10秒）：
```bash
cron add \
  --name "leader-election" \
  --schedule '{"kind": "every", "everyMs": 10000}' \
  --system-event "cd ~/clawd/clawster && python3 scripts/leader_watcher.py --node-id RouterLadderbot --once" \
  --agent main
```

**协作任务**（每10分钟）：
```bash
cron add \
  --name "agent-collaboration-1hao" \
  --schedule '{"kind": "cron", "expr": "*/10 * * * *"}' \
  --system-event "EXEC: ~/clawd/clawster/scripts/agent_collaboration.py --node-id RouterLadderbot --partner sx_squid_bot" \
  --agent main
```

### 一键部署新节点

使用 `join_cluster.sh` 脚本快速加入集群：

```bash
# 下载并执行
curl -fsSL https://raw.githubusercontent.com/YoungSx/clawster/main/scripts/join_cluster.sh | bash

# 或手动
git clone https://github.com/YoungSx/clawster.git
cd clawster
./scripts/join_cluster.sh my-node-01

# 编辑配置文件
vim config/secrets.json  # 填入你的Redis密码

# 测试连接
./test_connection.sh

# 启动节点
./start.sh
```

## 快速开始

### 1. 配置 Redis 连接

**方式一：配置文件（推荐）**

编辑 `config/secrets.json`（该文件已被 gitignore 排除）：

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

**方式二：环境变量**（优先级更高）

```bash
export REDIS_HOST=your-redis-host
export REDIS_PORT=11877
export REDIS_PASSWORD=your-password
export REDIS_DB=0
export OPENCLAW_NODE_ID=main-node
```

### 2. 配置节点参数

编辑 `config/config.json`：

```json
{
  "node": {
    "id": "main-node",           // 节点唯一标识
    "heartbeat_interval": 10,     // 心跳间隔（秒）
    "heartbeat_ttl": 90,          // 心跳过期时间（秒）
    "retry_count": 3,             // 失败重试次数
    "retry_delay": 1              // 重试间隔（秒）
  },
  "logging": {
    "level": "INFO",
    "max_bytes": 10485760,        // 日志文件最大 10MB
    "backup_count": 5             // 保留 5 个备份
  }
}
```

**配置说明：**
- `id`: 节点唯一标识（建议使用环境变量 `OPENCLAW_NODE_ID` 覆盖）
- `heartbeat_interval`: 心跳间隔（秒），推荐 10s
- `heartbeat_ttl`: 心跳过期时间（秒），推荐是间隔的 9 倍（90s）
- `retry_count`: 失败重试次数
- `retry_delay`: 重试间隔（秒）

### 3. 启动心跳（通过 OpenClaw Cron）

```bash
# 创建每 10 秒执行的心跳任务
openclaw cron add \
  --name "distributed-node-heartbeat" \
  --every 10s \
  --system-event "EXEC: ./scripts/heartbeat.py" \
  --agent main
```

### 4. 验证心跳

```bash
# 查看 cron job 列表
openclaw cron list

# 查看心跳日志
tail -f logs/heartbeat.log
```

## 核心组件

### heartbeat.py

节点心跳脚本，由 cron 调度执行：

- 每 10 秒（可配置）向 Redis 发送心跳
- 自动重试机制（失败时重试 3 次）
- 双向日志：本地文件 + 控制台 + syslog（可选）
- 配置从 `config/` 目录或环境变量读取

**手动测试：**
```bash
python3 scripts/heartbeat.py
```

### redis_client.py

纯 Python 实现的 Redis 客户端，零外部依赖：

- 使用标准库 `socket` 实现 RESP 协议
- 支持命令：HSET, HGET, SETEX, GET, DELETE
- 连接池管理
- 5 秒超时配置

### node_manager.py

节点生命周期管理：

- 节点注册/注销
- 状态检测
- 健康检查

### leader_election.py

Leader 选举逻辑：

- 基于 Redis RedLock 算法
- 自动故障转移
- 租约续期

## Redis Schema

| Key | Type | Description |
|-----|------|-------------|
| `openclaw:cluster:nodes` | Hash | 所有节点信息（field: node_id, value: JSON） |
| `hb:{node_id}` | String | 节点心跳 TTL（30秒过期） |
| `openclaw:cluster:leader` | String | 当前 leader 节点ID |

## 心跳机制

```
┌──────────┐     每10秒      ┌─────────┐     ┌─────────┐
│ Cron Job │ ──────────────▶ │  Script │ ──▶ │  Redis  │
└──────────┘                 └─────────┘     └─────────┘
                                     │              │
                                     ▼              ▼
                              logs/heartbeat.log  TTL=30s
                              (轮转 10MB)
```

**故障恢复：**
- 心跳失败自动重试 3 次
- 连续 3 次心跳丢失（30秒）标记为离线
- Leader 丢失时触发重新选举

## 日志查看

```bash
# 实时查看心跳日志
tail -f logs/heartbeat.log

# 查看最近 100 条
python3 -c "
import logging.handlers
handler = logging.handlers.RotatingFileHandler('logs/heartbeat.log')
# 或者直接使用 tail 命令
"
```

日志格式：
```
2026-02-02 10:53:18 INFO: ✅ 心跳发送成功 (attempt 1)
2026-02-02 10:53:28 WARNING: 心跳失败 (attempt 1): Connection refused，1秒后重试...
2026-02-02 10:53:30 INFO: ✅ 心跳发送成功 (attempt 2)
```

## 常见问题

### Q: 心跳脚本执行失败？

**检查步骤：**
1. Redis 配置是否正确（`config/secrets.json` 或环境变量）
2. 网络是否可达 Redis 服务器
3. 查看日志 `logs/heartbeat.log`

### Q: 如何修改心跳频率？

1. 修改 `config/config.json` 中的 `heartbeat_interval`
2. 删除旧 cron job：`openclaw cron delete <job-id>`
3. 创建新 job：使用新的 `--every` 参数

### Q: 多节点如何配置？

每个节点设置唯一的 `OPENCLAW_NODE_ID`：
```bash
export OPENCLAW_NODE_ID=node-002
```

## 环境要求

- Python 3.9+
- Redis 5.0+（支持 Streams）
- **无 pip 依赖**（纯 Python 标准库）

## 安全说明

- `config/secrets.json` 已加入 `.gitignore`，不会提交到版本控制
- 生产环境建议使用环境变量注入敏感信息
- Redis 密码建议使用强密码并定期轮换

## 相关文档

- [SKILL.md](./SKILL.md) - OpenClaw 技能元数据和完整配置说明
- `/app/docs/` - OpenClaw 官方文档
