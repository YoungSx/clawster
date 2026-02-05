#!/usr/bin/env python3
"""
OpenClaw Distributed - Failover Manager
Handles automatic failover and node recovery
"""

import json
import time
from typing import List, Dict, Any
import redis


class FailoverManager:
    """Manages node failover and recovery"""
    
    def __init__(self, redis_client: redis.Redis, config: dict):
        self.redis = redis_client
        self.config = config
        
    def mark_node_failed(self, node_id: str, reason: str = "heartbeat_timeout") -> bool:
        """Mark a node as failed and trigger failover"""
        log_entry = {
            'timestamp': time.time(),
            'node_id': node_id,
            'event': 'node_failed',
            'reason': reason
        }
        
        # Add to events stream
        self.redis.xadd('openclaw:cluster:events', log_entry)
        
        # Update node info
        node_data = self.redis.hget('openclaw:cluster:nodes', node_id)
        if node_data:
            node_info = json.loads(node_data)
            node_info['state'] = 'failed'
            node_info['failed_at'] = time.time()
            node_info['fail_reason'] = reason
            self.redis.hset('openclaw:cluster:nodes', node_id, json.dumps(node_info))
        
        print(f"[FailoverManager] Node {node_id} marked as failed: {reason}")
        
        # Trigger failover actions on sessions, etc.
        self._trigger_failover_actions(node_id)
        
        return True
    
    def _trigger_failover_actions(self, failed_node: str) -> None:
        """Execute failover actions for the failed node"""
        # 1. Reassign active sessions
        self._migrate_sessions(failed_node)
        
        # 2. Notify other nodes
        failover_event = {
            'type': 'failover',
            'failed_node': failed_node,
            'timestamp': time.time(),
            'action': 'sessions_migrated'
        }
        self.redis.publish('openclaw:cluster:failover', json.dumps(failover_event))
    
    def _migrate_sessions(self, from_node: str) -> int:
        """Migrate active sessions from failed node"""
        # Find sessions owned by failed node
        pattern = f'openclaw:cluster:sessions:*'
        migrated = 0
        
        for key in self.redis.scan_iter(match=pattern):
            session_data = self.redis.get(key)
            if session_data:
                session = json.loads(session_data)
                if session.get('node_id') == from_node:
                    session['node_id'] = 'migrating'
                    session['migrated_from'] = from_node
                    session['migrated_at'] = time.time()
                    self.redis.setex(key, 3600, json.dumps(session))
                    migrated += 1
        
        print(f"[FailoverManager] Migrated {migrated} sessions from {from_node}")
        return migrated
    
    def recover_node(self, node_id: str) -> bool:
        """Reintegrate a recovered node into cluster"""
        node_data = self.redis.hget('openclaw:cluster:nodes', node_id)
        
        if not node_data:
            print(f"[FailoverManager] Node {node_id} not found in registry")
            return False
        
        node_info = json.loads(node_data)
        
        if node_info.get('state') != 'failed':
            print(f"[FailoverManager] Node {node_id} is not in failed state")
            return False
        
        # Mark as recovering
        node_info['state'] = 'suspected'  # Will be promoted to follower
        node_info['recovered_at'] = time.time()
        node_info['previous_failure'] = {
            'failed_at': node_info.pop('failed_at', None),
            'reason': node_info.pop('fail_reason', None)
        }
        self.redis.hset('openclaw:cluster:nodes', node_id, json.dumps(node_info))
        
        # Add recovery event
        log_entry = {
            'timestamp': time.time(),
            'node_id': node_id,
            'event': 'node_recovered'
        }
        self.redis.xadd('openclaw:cluster:events', log_entry)
        
        print(f"[FailoverManager] Node {node_id} marked for recovery")
        return True
    
    def get_failed_nodes(self) -> List[str]:
        """Get list of failed nodes"""
        nodes = self.redis.hgetall('openclaw:cluster:nodes')
        failed = []
        
        for node_id, node_data in nodes.items():
            info = json.loads(node_data)
            if info.get('state') == 'failed':
                failed.append(node_id)
        
        return failed
    
    def health_check(self) -> Dict[str, Any]:
        """Run comprehensive health check"""
        nodes = self.redis.hgetall('openclaw:cluster:nodes')
        
        status = {
            'total': len(nodes),
            'healthy': 0,
            'failed': 0,
            'suspected': 0,
            'unknown': 0,
            'nodes': {}
        }
        
        for node_id, node_data in nodes.items():
            info = json.loads(node_data)
            state = info.get('state', 'unknown')
            
            status['nodes'][node_id] = {
                'state': state,
                'last_seen': info.get('last_seen'),
                'capabilities': info.get('capabilities', [])
            }
            
            if state in ['leader', 'follower']:
                status['healthy'] += 1
            elif state == 'failed':
                status['failed'] += 1
            elif state == 'suspected':
                status['suspected'] += 1
            else:
                status['unknown'] += 1
        
        return status


if __name__ == '__main__':
    # Test code
    print("FailoverManager module loaded")
    print("Usage: Import and use with NodeManager")
