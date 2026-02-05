#!/usr/bin/env python3
"""
OpenClaw Distributed Skill - Node Heartbeat Script
更新 Redis 集群中的节点心跳，支持重试机制和双向日志。
集成 Leader 选举状态。

配置从外部文件读取：
- 通用配置: ../config/config.json
- 敏感信息: ../config/secrets.json 或环境变量
"""

import sys
import os
import time
import json
import logging
import logging.handlers
from pathlib import Path

# 添加脚本目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from redis_client import RedisClient
from leader_election import LeaderElection

# 获取项目根目录
SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
CONFIG_DIR = PROJECT_DIR / 'config'
LOG_DIR = PROJECT_DIR / 'logs'

def load_config():
    """加载通用配置"""
    config_path = CONFIG_DIR / 'config.json'
    if config_path.exists():
        with open(config_path, 'r') as f:
            return json.load(f)
    # 默认配置
    return {
        "node": {
            "id": os.getenv('OPENCLAW_NODE_ID', ''),
            "heartbeat_interval": 10,
            "heartbeat_ttl": 30,
            "retry_count": 3,
            "retry_delay": 1,
            "leader_ttl": 30
        },
        "logging": {
            "level": "INFO",
            "max_bytes": 10485760,
            "backup_count": 5
        }
    }


def validate_config(config):
    """校验并修复配置"""
    node_id = config.get('node', {}).get('id', '').strip()
    if not node_id:
        # 1. 尝试从环境变量获取
        node_id = os.getenv('OPENCLAW_NODE_ID', '').strip()
        if node_id:
            config['node']['id'] = node_id
        else:
            # 2. 自动生成唯一 ID
            import uuid
            node_id = f"node-{uuid.uuid4().hex[:8]}"
            config['node']['id'] = node_id
        logger.warning(f"⚠️ node.id 为空，已自动设置: {node_id}")
    return config

def _resolve_env_var(value: str) -> str:
    """解析模板变量，如 ${VAR_NAME} 替换为环境变量值"""
    import re
    # 匹配 ${VAR_NAME} 格式
    match = re.match(r'^\$\{(.+)\}$', str(value))
    if match:
        env_name = match.group(1)
        env_value = os.getenv(env_name)
        if env_value:
            return env_value
        else:
            raise RuntimeError(f"模板变量 ${{{env_name}}} 未设置环境变量")
    return value

def load_secrets():
    """加载敏感配置（统一使用 secrets.json，优先级最高）"""

    secrets_path = CONFIG_DIR / 'secrets.json'

    # 首先检查 secrets.json 是否存在
    if not secrets_path.exists():
        raise RuntimeError(f"secrets.json 不存在: {secrets_path}")

    try:
        with open(secrets_path, 'r') as f:
            data = json.load(f)
            redis_data = data.get('redis', {})

            # 从 secrets.json 读取基础配置，并解析模板变量
            redis_config = {
                'host': _resolve_env_var(redis_data.get('host', '')),
                'port': redis_data.get('port', 0),
                'password': _resolve_env_var(redis_data.get('password', '')),
                'db': redis_data.get('db', 0)
            }

    except Exception as e:
        raise RuntimeError(f"无法读取 secrets.json: {e}")

    # 验证必要配置
    if not all([redis_config['host'], redis_config['password']]):
        raise RuntimeError("Redis 配置不完整：secrets.json 中缺少 host 或 password")

    # 环境变量作为可选覆盖（仅在 secrets.json 值为空时使用）
    if not redis_config['host']:
        redis_config['host'] = os.getenv('REDIS_HOST')
    if not redis_config['port']:
        redis_config['port'] = int(os.getenv('REDIS_PORT', 11877))
    if not redis_config['password']:
        redis_config['password'] = os.getenv('REDIS_PASSWORD')
    if not redis_config.get('db'):
        redis_config['db'] = int(os.getenv('REDIS_DB', 0))

    # 确保端口是整数
    if isinstance(redis_config['port'], str):
        redis_config['port'] = int(redis_config['port'])

    return redis_config

# 加载配置
config = load_config()
config = validate_config(config)  # 校验并修复 node.id
secrets = load_secrets()

# 配置参数
REDIS_CONFIG = secrets
NODE_ID = config['node']['id']
assert NODE_ID, "node.id 不能为空！请在 config.json 中设置或设置 OPENCLAW_NODE_ID 环境变量"
HEARTBEAT_TTL = config['node']['heartbeat_ttl']
LEADER_TTL = config['node'].get('leader_ttl', 30)
RETRY_COUNT = config['node']['retry_count']
RETRY_DELAY = config['node']['retry_delay']

# 确保日志目录存在
LOG_DIR.mkdir(parents=True, exist_ok=True)

# 配置双向日志
logger = logging.getLogger('heartbeat')
logger.setLevel(getattr(logging, config['logging']['level']))

if logger.handlers:
    logger.handlers.clear()

# 1. Syslog 处理器
if Path('/dev/log').exists():
    try:
        syslog_handler = logging.handlers.SysLogHandler(address='/dev/log')
        syslog_handler.setLevel(logging.INFO)
        syslog_formatter = logging.Formatter('clawster: %(message)s')
        syslog_handler.setFormatter(syslog_formatter)
        logger.addHandler(syslog_handler)
    except Exception:
        pass

# 2. 本地文件处理器
file_handler = logging.handlers.RotatingFileHandler(
    LOG_DIR / 'heartbeat.log',
    maxBytes=config['logging']['max_bytes'],
    backupCount=config['logging']['backup_count']
)
file_handler.setLevel(logging.DEBUG)
file_formatter = logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

# 3. 控制台处理器
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)


def get_leader_info(client: RedisClient) -> dict:
    """获取当前 Leader 信息"""
    try:
        from leader_election import LeaderElection
        election = LeaderElection(node_id=NODE_ID, redis_client=client, lock_ttl=LEADER_TTL)
        return election.get_info()
    except Exception as e:
        logger.debug(f"获取 Leader 信息失败: {e}")
        return {'current_leader': None, 'is_leader': False}


def send_heartbeat(retry_count=RETRY_COUNT, retry_delay=RETRY_DELAY):
    """发送心跳到 Redis，包含 Leader 状态"""
    attempt = 0
    client = RedisClient(
        host=REDIS_CONFIG['host'],
        port=REDIS_CONFIG['port'],
        password=REDIS_CONFIG['password'],
        db=REDIS_CONFIG['db'],
        socket_timeout=5
    )

    while attempt < retry_count:
        try:
            attempt += 1
            logger.debug(f"心跳尝试 {attempt}/{retry_count}...")

            client.connect()

            # 获取 Leader 信息
            leader_info = get_leader_info(client)
            is_leader = leader_info.get('is_leader', False)
            current_leader = leader_info.get('current_leader')
            leader_ttl = leader_info.get('ttl_remaining', -1)

            # 准备心跳数据
            heartbeat_data = {
                'timestamp': time.time(),
                'is_leader': is_leader,
                'leader_ttl': leader_ttl,
            }

            node_info = {
                'node_id': NODE_ID,
                'is_leader': is_leader,
                'current_leader': current_leader,
            }

            # 设置节点信息和心跳
            client.hset('openclaw:cluster:nodes', NODE_ID, json.dumps(node_info))
            client.setex(f'hb:{NODE_ID}', HEARTBEAT_TTL, json.dumps(heartbeat_data))

            status_emoji = '👑' if is_leader else '📡'
            logger.info(f"{status_emoji} 心跳发送成功 | is_leader={is_leader} | leader_ttl={leader_ttl}s")

            client.close()
            return True, is_leader

        except Exception as e:
            client.close()

            if attempt < retry_count:
                logger.warning(f"心跳失败 (attempt {attempt}): {e}，{retry_delay}秒后重试...")
                time.sleep(retry_delay)
            else:
                logger.error(f"心跳失败，已达最大重试次数 {retry_count}: {e}")

    return False, False


def main():
    """主函数"""
    logger.debug(f"开始执行心跳脚本，节点: {NODE_ID}")

    success, is_leader = send_heartbeat()

    if success:
        logger.debug("心跳脚本执行完成")
        sys.exit(0)
    else:
        logger.error("心跳脚本执行失败")
        sys.exit(1)


if __name__ == '__main__':
    main()
