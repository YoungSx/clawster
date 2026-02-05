# Redis 配置统一方案 - 详细说明

## 📋 概述

本项目采用统一的 Redis 配置管理方案，所有脚本从同一个配置文件 `secrets.json` 读取连接信息，确保分布式环境中各节点配置一致性。

## 🏗️ 架构

```
                    ┌─────────────────────┐
                    │   secrets.json      │
                    │   (唯一配置来源)     │
                    └──────────┬──────────┘
                               │
                    ┌──────────┴──────────┐
                    │   config_loader.py  │
                    │   (统一加载器)       │
                    └──────────┬──────────┘
                               │
           ┌───────────────────┼───────────────────┐
           │                   │                   │
    ┌──────▼──────┐     ┌──────▼──────┐     ┌──────▼──────┐
    │ heartbeat.py│     │leader_watcher│    │verify_cluster│
    └──────┬──────┘     └──────┬──────┘     └──────┬──────┘
           │                   │                   │
           └───────────────────┼───────────────────┘
                               │
                    ┌──────────┴──────────┐
                    │   Redis Server      │
                    │ redis-11877...      │
                    └─────────────────────┘
```

## 📁 文件结构

```
clawster/
├── config/
│   ├── config.json          # 通用配置（节点 ID、心跳间隔等）
│   └── secrets.json         # 敏感配置（Redis 连接信息）⭐ 重要
├── scripts/
│   ├── config_loader.py     # 统一配置加载器 ⭐ 新增
│   ├── heartbeat.py         # 心跳脚本（已修复）
│   ├── agent_collaboration.py  # 协作脚本（已修复）
│   ├── leader_watcher.py    # Leader 监控（已修复）
│   ├── test_leader_election.py # 测试脚本（已修复）
│   └── verify_cluster.py    # 验证脚本（已修复）
└── REDIS_CONFIG_UNIFICATION.md  # 本文档
```

## 🔐 secrets.json 配置格式

```json
{
  "redis": {
    "host": "redis-11877...........cloud.redislabs.com`",
    "port": 11877,
    "password": "your_password_here",
    "db": 0
  }
}
```

### 字段说明

| 字段 | 必填 | 说明 |
|------|------|------|
| `host` | ✅ | Redis 服务器地址 |
| `port` | ✅ | Redis 端口，默认 11877 |
| `password` | ✅ | 认证密码 |
| `db` | ❌ | 数据库编号，默认 0 |

## 🚀 使用方法

### 方法 1: 使用统一配置加载器（推荐）

```python
#!/usr/bin/env python3
import sys
import os
from pathlib import Path

# 添加脚本目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config_loader import get_redis_config, get_node_config

# 获取 Redis 配置
redis_config = get_redis_config()
# {'host': '...', 'port': 11877, 'password': '...', 'db': 0}

# 获取节点配置
node_config = get_node_config()
# {'node': {'id': '...', 'heartbeat_interval': 10, ...}}
```

### 方法 2: 直接读取 secrets.json（不推荐）

```python
import json
from pathlib import Path

secrets_path = Path(__file__).parent.parent / 'config' / 'secrets.json'
with open(secrets_path) as f:
    config = json.load(f)
    
redis_config = config['redis']
```

### 方法 3: 环境变量覆盖（仅备选）

如果 secrets.json 中的值为空，会尝试从环境变量读取：

```bash
export REDIS_HOST="redis-11877...........cloud.redislabs.com`"
export REDIS_PORT="11877"
export REDIS_PASSWORD="your_password"
export REDIS_DB="0"
```

## 📝 修复的脚本列表

| 脚本 | 修复内容 |
|------|----------|
| `config_loader.py` | 🆕 新建，统一配置加载器 |
| `heartbeat.py` | 重写 `load_secrets()` 函数，优先使用 secrets.json |
| `agent_collaboration.py` | 导入 `config_loader`，移除重复配置加载 |
| `leader_watcher.py` | 使用 `config_loader.get_redis_config()` |
| `test_leader_election.py` | 使用 `config_loader` |
| `verify_cluster.py` | 使用 `config_loader` |

## 🔧 心跳机制

### 键命名规范（v1.1 协议）

| 键名 | 类型 | 说明 |
|------|------|------|
| `hb:bot1` | String | bot1 心跳，30秒 TTL |
| `hb:bot2` | String | bot2 心跳，30秒 TTL |
| `inbox:bot1` | List | bot1 消息队列 |
| `inbox:bot2` | List | bot2 消息队列 |
| `openclaw:cluster:nodes` | Hash | 集群节点注册表 |

### 心跳数据结构

```json
{
  "status": "online",
  "ts": "2026-02-04T04:58:14Z",
  "node": "bot2"
}
```

## 🧪 测试命令

```bash
# 1. 测试配置加载
cd /home/node/clawster/scripts
python3 config_loader.py

# 2. 写入并验证心跳
python3 << 'EOF'
import redis, json, time
import sys
sys.path.insert(0, '.')
from config_loader import get_redis_config

cfg = get_redis_config()
r = redis.Redis(**cfg, socket_timeout=10)

# 写入心跳
r.setex('hb:bot2', 30, json.dumps({
    "status": "online",
    "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
}))

# 验证
print(f"hb:bot2 = {r.get('hb:bot2')}")
print(f"所有键: {r.keys('*')}")
EOF

# 3. 验证集群状态
python3 verify_cluster.py
```

## ⚠️ 常见问题

### Q1: DNS 解析失败

**错误:** `socket.gaierror: [Errno -2] Name or service not known`

**解决方案:**
1. 确认 `secrets.json` 中的 `host` 正确
2. 检查网络连接: `ping redis-11877...........cloud.redislabs.com`
3. 尝试使用 IP 地址代替域名

### Q2: 连接超时

**错误:** `redis.exceptions.ConnectionError: Timeout`

**解决方案:**
1. 检查端口是否正确（默认 11877）
2. 检查防火墙设置
3. 验证密码是否正确

### Q3: 认证失败

**错误:** `AUTH failed`

**解决方案:**
1. 确认 `password` 字段正确
2. 检查是否有特殊字符需要转义

## 📚 相关文档

- `ARCHITECTURE.md` - 系统架构文档
- `SKILL.md` - 分布式 Skill 文档
- `README.md` - 项目说明

## 🔄 版本历史

| 版本 | 日期 | 说明 |
|------|------|------|
| v1.0 | 2026-02-03 | 初始版本，各自配置 |
| v1.1 | 2026-02-04 | 统一配置方案，修复 DNS 问题 |

## 👥 维护者

- bot1 (RouterLadderbot)
- bot2 (sx_squid_bot)

---

**问题反馈:** 请在 GitHub Issues 中提交
