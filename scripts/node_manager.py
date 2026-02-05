#!/usr/bin/env python3
"""OpenClaw Distributed - Node Manager
Manages node lifecycle: registration, heartbeat, state transitions
Lightweight: uses redis_client (no external deps)
"""

import json
import time
import sys
import os
from datetime import datetime
from typing import Dict, Any

try:
    from redis_client import RedisClient
except ImportError:
    from .redis_client import RedisClient


class NodeState:
    FOLLOWER = "follower"
    CANDIDATE = "candidate"
    LEADER = "leader"


class NodeManager:
    def __init__(self, node_id: str, config: Dict[str, Any]):
        self.node_id = node_id
        self.config = config
        self.state = NodeState.FOLLOWER
        self.term = 0
        self.leader_id = None
        self.last_heartbeat = time.time()
        
        redis_cfg = config.get('redis', {})
        self.redis = RedisClient(
            host=redis_cfg.get('host', 'localhost'),
            port=redis_cfg.get('port', 6379),
            password=redis_cfg.get('password'),
            db=redis_cfg.get('db', 0),
            socket_timeout=5.0
        )
        
        heartbeat_cfg = config.get('heartbeat', {})
        self.heartbeat_interval = heartbeat_cfg.get('interval_ms', 5000) / 1000
        self.heartbeat_timeout = heartbeat_cfg.get('timeout_ms', 15000) / 1000

    def register_node(self) -> bool:
        node_info = {
            'node_id': self.node_id,
            'state': self.state,
            'term': self.term,
            'registered_at': datetime.utcnow().isoformat(),
            'capabilities': self.config.get('capabilities', ['default'])
        }
        self.redis.hset('openclaw:cluster:nodes', self.node_id, json.dumps(node_info))
        print(f"[NodeManager] Node {self.node_id} registered")
        return True

    def send_heartbeat(self) -> None:
        heartbeat_key = f'hb:{self.node_id}'
        heartbeat_data = json.dumps({
            'timestamp': time.time(),
            'state': self.state,
            'term': self.term
        })
        self.redis.setex(heartbeat_key, int(self.heartbeat_timeout * 2), heartbeat_data)

    def check_peers(self) -> list:
        nodes = self.redis.hgetall('openclaw:cluster:nodes')
        failed = []
        now = time.time()
        for nid, _ in nodes.items():
            if nid == self.node_id:
                continue
            hb = self.redis.get(f'hb:{nid}')
            if not hb:
                failed.append(nid)
                continue
            ts = json.loads(hb).get('timestamp', 0)
            if now - ts > self.heartbeat_timeout:
                failed.append(nid)
        return failed

    def run(self):
        print(f"[NodeManager] Starting {self.node_id}")
        self.register_node()
        try:
            while True:
                self.send_heartbeat()
                if self.state in [NodeState.LEADER, NodeState.CANDIDATE]:
                    failed = self.check_peers()
                    if failed:
                        print(f"[NodeManager] Failed nodes: {failed}")
                time.sleep(self.heartbeat_interval)
        except KeyboardInterrupt:
            print(f"[NodeManager] Shutting down {self.node_id}")
            self.redis.hdel('openclaw:cluster:nodes', self.node_id)
            self.redis.close()


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--node-id', required=True)
    parser.add_argument('--config', default='./config.json')
    args = parser.parse_args()
    
    with open(os.path.expanduser(args.config)) as f:
        cfg = json.load(f).get('cluster', {})
    
    NodeManager(args.node_id, cfg).run()
