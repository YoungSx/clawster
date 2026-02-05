#!/usr/bin/env python3
"""
集群状态验证脚本 - 确保改名后检测正常
"""

import sys
import json
import time
from pathlib import Path

sys.path.insert(0, Path(__file__).parent)
from redis_client import RedisClient
from node_discovery import NodeRegistry
from config_loader import get_redis_config


def verify_cluster():
    redis_cfg = get_redis_config()
    redis = RedisClient(**redis_cfg)
    redis.connect()
    
    print('=' * 50)
    print('集群状态验证')
    print('=' * 50)
    
    # 1. 使用动态发现（不打死名字）
    print('\n1️⃣  动态Leader发现')
    leader = redis.get('openclaw:cluster:leader_lock')
    if leader:
        leader_name = leader.split(':')[0] if ':' in leader else leader
        print(f'   ✅ Leader: {leader_name}')
    else:
        print('   ⚠️  无Leader')
    
    # 2. 注册表状态
    print('\n2️⃣  节点注册表')
    registry = NodeRegistry(redis, 'verify-script')
    nodes = registry.get_all_nodes()
    online = [n for n in nodes if n.get('is_online')]
    print(f'   总计: {len(nodes)} 个')
    print(f'   在线: {len(online)} 个')
    
    for node in nodes:
        status = '🟢' if node.get('is_online') else '🔴'
        leader_flag = '👑' if node.get('is_leader') else '  '
        print(f'   {status} {leader_flag} {node["node_id"]} ({node.get("age_seconds", 0):.0f}s)')
    
    # 3. 心跳检测（动态获取所有）
    print('\n3️⃣  心跳状态')
    all_nodes = redis.hgetall('openclaw:cluster:nodes')
    hb_status = []
    for node_id in all_nodes:
        hb = redis.get(f'hb:{node_id}')
        if hb:
            data = json.loads(hb)
            age = time.time() - data['timestamp']
            is_leader = data.get('is_leader', False)
            hb_status.append({
                'node_id': node_id,
                'age': age,
                'is_leader': is_leader,
                'online': age < 60
            })
            
    for h in hb_status:
        status = '🟢' if h['online'] else '🔴'
        leader = '👑' if h['is_leader'] else '  '
        print(f'   {status} {leader} {h["node_id"]}: {h["age"]:.0f}s')
    
    # 4. 投诉检测
    print('\n4️⃣  通信频道')
    chat_keys = [
        'openclaw:chat:RouterLadderbot',
        'openclaw:chat:sx_squid_bot',
        'openclaw:chat:main-node'
    ]
    for key in chat_keys:
        count = redis.llen(key)
        print(f'   📨 {key}: {count} 条')
    
    print('\n' + '=' * 50)
    print('验证结论')
    print('=' * 50)
    
    if leader and len([h for h in hb_status if h['online']]) >= 1:
        print('✅ 集群状态正常')
        print(f'✅ Leader: {leader_name}')
        print(f'✅ 在线节点: {len([h for h in hb_status if h["online"]])}')
    else:
        print('⚠️  集群需要关注')
        if not leader:
            print('❌ 无Leader')
        if len([h for h in hb_status if h['online']]) == 0:
            print('❌ 无在线节点')
    
    return leader is not None


if __name__ == '__main__':
    verify_cluster()
