#!/usr/bin/env python3
"""测试修复后的Redis客户端"""
import sys
import json
sys.path.insert(0, 'scripts')

from redis_client_fixed import RedisClient

print('测试修复版Redis客户端')
print('=' * 50)

with open('config/secrets.json') as f:
    cfg = json.load(f)

r = RedisClient(**cfg['redis'])
r.connect()

# 测试1: setex
print('\n1. 测试 SETEX...')
try:
    result = r.setex('test:fix:setex', 90, 'hello')
    print(f'   ✅ SETEX成功: {result}')
except Exception as e:
    print(f'   ❌ SETEX失败: {e}')

# 验证是否写入
val = r.get('test:fix:setex')
print(f'   验证GET: {val}')

# 测试2: hset/hgetall
print('\n2. 测试 HSET...')
try:
    result = r.hset('test:fix:hash', 'field1', 'value1')
    print(f'   ✅ HSET成功: {result}')
except Exception as e:
    print(f'   ❌ HSET失败: {e}')

all_fields = r.hgetall('test:fix:hash')
print(f'   验证HGETALL: {all_fields}')

# 测试3: 真实心跳
print('\n3. 测试心跳写入...')
import time
NODE_ID = 'test-node'
try:
    hb_data = {
        'timestamp': time.time(),
        'is_leader': False,
        'leader_ttl': -1
    }
    r.setex(f'hb:{NODE_ID}', 90, json.dumps(hb_data))
    print('   ✅ 心跳SETEX成功')

    # 验证
    hb = r.get(f'hb:{NODE_ID}')
    if hb:
        print(f'   ✅ 验证GET成功: 键存在')
    else:
        print('   ❌ 验证失败: 键不存在!')
except Exception as e:
    print(f'   ❌ 心跳测试失败: {e}')

print('\n修复版测试完成!')
