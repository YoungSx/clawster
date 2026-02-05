#!/usr/bin/env python3
"""
统一配置加载器 - 所有脚本使用 secrets.json

原则:
1. 统一使用 secrets.json 作为 Redis 配置来源
2. 环境变量作为备用覆盖
3. 所有脚本必须导入此模块获取 Redis 配置

使用方式:
    from config_loader import get_redis_config
    redis_config = get_redis_config()
    r = RedisClient(**redis_config)
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, Optional

# 全局缓存
_config_cache = None
_config_loaded = False


def get_config_dir() -> Path:
    """获取配置目录"""
    # 优先使用环境变量
    if os.getenv('CLAWSTER_CONFIG_DIR'):
        return Path(os.getenv('CLAWSTER_CONFIG_DIR'))
    
    # 默认路径
    script_dir = Path(__file__).parent
    config_dir = script_dir.parent / 'config'
    
    # 备选路径
    alt_paths = [
        Path('/home/shangxin/clawd/clawster/config'),
        Path('/root/clawster/config'),
        Path('/home/node/clawster/config'),
    ]
    
    for alt in alt_paths:
        if alt.exists():
            return alt
    
    return config_dir


def get_secrets_path() -> Optional[Path]:
    """获取 secrets.json 路径"""
    config_dir = get_config_dir()
    secrets_path = config_dir / 'secrets.json'
    
    if secrets_path.exists():
        return secrets_path
    
    return None


def get_redis_config() -> Dict[str, Any]:
    """
    获取 Redis 配置（统一使用 secrets.json）
    
    Returns:
        {
            'host': str,
            'port': int,
            'password': str,
            'db': int
        }
    
    Raises:
        RuntimeError: secrets.json 不存在或配置不完整
    """
    global _config_cache, _config_loaded
    
    # 如果已经加载过，直接返回缓存
    if _config_loaded and _config_cache is not None:
        return _config_cache
    
    secrets_path = get_secrets_path()
    
    if not secrets_path:
        raise RuntimeError(f"secrets.json 不存在！搜索路径: {get_config_dir()}")
    
    try:
        with open(secrets_path, 'r') as f:
            data = json.load(f)
            redis_data = data.get('redis', {})
            
            # 基础配置
            redis_config = {
                'host': redis_data.get('host'),
                'port': redis_data.get('port', 11877),
                'password': redis_data.get('password'),
                'db': redis_data.get('db', 0)
            }
            
    except json.JSONDecodeError as e:
        raise RuntimeError(f"secrets.json 格式错误: {e}")
    except Exception as e:
        raise RuntimeError(f"读取 secrets.json 失败: {e}")
    
    # 验证必要配置
    if not all([redis_config['host'], redis_config['password']]):
        raise RuntimeError("Redis 配置不完整：secrets.json 中缺少 host 或 password")
    
    # 环境变量作为可选覆盖（仅在 secrets.json 值无效时使用）
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
    
    # 缓存配置
    _config_cache = redis_config
    _config_loaded = True
    
    return redis_config


def get_node_config() -> Dict[str, Any]:
    """获取节点配置"""
    config_dir = get_config_dir()
    config_path = config_dir / 'config.json'
    
    if config_path.exists():
        with open(config_path, 'r') as f:
            return json.load(f)
    
    # 默认配置
    return {
        'node': {
            'id': os.getenv('OPENCLAW_NODE_ID', ''),
            'heartbeat_interval': 10,
            'heartbeat_ttl': 30,
            'retry_count': 3,
            'retry_delay': 1,
            'leader_ttl': 60
        },
        'logging': {
            'level': 'INFO'
        }
    }


def validate_node_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """校验并修复节点配置"""
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
        print(f"⚠️ node.id 为空，已自动设置: {node_id}")
    return config


def reload_config():
    """强制重新加载配置"""
    global _config_cache, _config_loaded
    _config_cache = None
    _config_loaded = False
    return get_redis_config()


if __name__ == '__main__':
    # 测试配置加载
    try:
        config = get_redis_config()
        print("✅ Redis 配置加载成功:")
        print(f"  host: {config['host']}")
        print(f"  port: {config['port']}")
        print(f"  db: {config['db']}")
        print(f"  password: {'*' * len(config['password'])}")
    except Exception as e:
        print(f"❌ 配置加载失败: {e}")
