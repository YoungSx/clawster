#!/usr/bin/env python3
"""Start as Leader node"""
import json
import time
import sys
sys.path.insert(0, '/home/shangxin/clawd/skills/clawster/scripts')

from redis_client import RedisClient

# Load config
with open('/home/shangxin/clawd/skills/clawster/config.json') as f:
    config = json.load(f)['cluster']

redis_cfg = config['redis']
r = RedisClient(
    host=redis_cfg['host'],
    port=redis_cfg['port'],
    password=redis_cfg['password'],
    db=redis_cfg.get('db', 0)
)
r.connect()

node_id = "routerladderbot-node"
term = 1

print(f"[Leader] Starting {node_id}...")

# Register as leader
node_info = {
    'node_id': node_id,
    'state': 'leader',
    'term': term,
    'registered_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
    'capabilities': ['leader', 'task-assigner']
}
r.hset('openclaw:cluster:nodes', node_id, json.dumps(node_info))
print(f"[Leader] Registered as LEADER")

# Set leader lock
lock_key = 'openclaw:cluster:leader:lock'
lock_value = f"{node_id}:{term}"
r.delete(lock_key)
r.setex(lock_key, 60, lock_value)

leader_data = {'node_id': node_id, 'term': term, 'elected_at': time.time()}
r.setex('openclaw:cluster:leader', 60, json.dumps(leader_data))
print(f"[Leader] Acquired leadership (term {term})")

# Heartbeat loop
print(f"[Leader] Heartbeat started...")
try:
    while True:
        r.setex(lock_key, 60, lock_value)
        r.setex('openclaw:cluster:leader', 60, json.dumps(leader_data))
        hb_data = json.dumps({'timestamp': time.time(), 'state': 'leader', 'term': term})
        r.setex(f'hb:{node_id}', 30, hb_data)
        time.sleep(5)
except KeyboardInterrupt:
    print(f"\n[Leader] Stopping...")
    r.delete('openclaw:cluster:leader')
    r.delete(lock_key)
    print(f"[Leader] Stepped down")
