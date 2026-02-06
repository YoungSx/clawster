#!/usr/bin/env python3
"""
OpenClaw Distributed - Secure Config Loader
重构版：
1. 优先级：环境变量 > secrets.json > 默认值
2. 安全性：移除敏感路径自动搜索
3. 鲁棒性：支持无配置文件纯环境启动
"""
import os
import json
from pathlib import Path
from typing import Dict, Any, Optional

# 全局缓存
_config_cache = None
_config_loaded = False


def get_config_dir() -> Path:
    """获取配置目录（安全版）"""
    # 1. 优先使用显式环境变量
    if os.getenv('CLAWSTER_CONFIG_DIR'):
        return Path(os.getenv('CLAWSTER_CONFIG_DIR'))

    # 2. 默认项目内路径
    script_dir = Path(__file__).parent
    return script_dir.parent / 'config'


def get_redis_config() -> Dict[str, Any]:
    """
    获取 Redis 配置（优先级：ENV > secrets.json > Defaults）
    """
    global _config_cache, _config_loaded

    if _config_loaded and _config_cache is not None:
        return _config_cache

    config = {
        'host': None,
        'port': 11877,
        'password': None,
        'db': 0
    }

    # --- 1. 尝试从 secrets.json 加载 ---
    secrets_path = get_config_dir() / 'secrets.json'
    if secrets_path.exists():
        try:
            with open(secrets_path, 'r') as f:
                data = json.load(f)
                redis_data = data.get('redis', {})
                config['host'] = redis_data.get('host')
                config['port'] = redis_data.get('port', config['port'])
                config['password'] = redis_data.get('password')
                config['db'] = redis_data.get('db', config['db'])
        except Exception as e:
            print(f"⚠️ 读取 secrets.json 失败: {e}")

    # --- 2. 环境变量覆盖 (最高优先级) ---
    env_host = os.getenv('REDIS_HOST')
    if env_host: config['host'] = env_host

    env_port = os.getenv('REDIS_PORT')
    if env_port: config['port'] = int(env_port)

    env_pass = os.getenv('REDIS_PASSWORD')
    if env_pass: config['password'] = env_pass

    env_db = os.getenv('REDIS_DB')
    if env_db: config['db'] = int(env_db)

    # --- 3. 验证必要配置 ---
    if not config['host'] or not config['password']:
        raise RuntimeError(
            f"Redis 配置不完整！缺失 host 或 password。\n"
            f"检测路径: {secrets_path}\n"
            f"当前配置: host={config['host']}, port={config['port']}, db={config['db']}"
        )

    # 强制端口为整数
    config['port'] = int(config['port'])

    _config_cache = config
    _config_loaded = True
    return config


def get_node_config() -> Dict[str, Any]:
    """获取节点配置"""
    config_path = get_config_dir() / 'config.json'
    if config_path.exists():
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except: pass

    return {
        'node': {
            'id': os.getenv('OPENCLAW_NODE_ID', ''),
            'heartbeat_interval': 10,
            'heartbeat_ttl': 30,
            'retry_count': 3,
            'retry_delay': 1,
            'leader_ttl': 60
        },
        'logging': {'level': 'INFO'}
    }

def reload_config():
    global _config_cache, _config_loaded
    _config_cache = None
    _config_loaded = False
    return get_redis_config()

if __name__ == '__main__':
    try:
        cfg = get_redis_config()
        print(f"✅ 配置加载成功: {cfg['host']}:{cfg['port']} (DB: {cfg['db']})")
    except Exception as e:
        print(f"❌ 配置失败: {e}")
