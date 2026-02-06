#!/usr/bin/env python3
"""
OpenClaw Distributed - Failover Manager
Handles automatic failover and node recovery
"""

import json
import time
from typing import List, Dict, Any
import redis
from redis import exceptions as redis_exceptions


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
        
        try:
            # Add to events stream
            self.redis.xadd('openclaw:cluster:events', log_entry)
        except redis_exceptions.RedisError as e:
            print(f"[FailoverManager] ERROR: Failed to add node failed event to Redis stream for {node_id}: {e}")
            return False # Critical failure, cannot mark node failed properly

        try:
            # Update node info
            node_data = self.redis.hget('openclaw:cluster:nodes', node_id)
            if node_data:
                try:
                    node_info = json.loads(node_data)
                except json.JSONDecodeError as e:
                    print(f"[FailoverManager] WARNING: Failed to decode node data for {node_id}: {e}. Skipping update.")
                    node_info = {} # Provide a default empty dict to avoid further errors

                node_info['state'] = 'failed'
                node_info['failed_at'] = time.time()
                node_info['fail_reason'] = reason
                self.redis.hset('openclaw:cluster:nodes', node_id, json.dumps(node_info))
            else:
                print(f"[FailoverManager] Node {node_id} not found in Redis when marking as failed. Creating new entry.")
                node_info = {
                    'node_id': node_id,
                    'state': 'failed',
                    'failed_at': time.time(),
                    'fail_reason': reason
                }
                self.redis.hset('openclaw:cluster:nodes', node_id, json.dumps(node_info))
        except redis_exceptions.RedisError as e:
            print(f"[FailoverManager] ERROR: Failed to update node info for {node_id} in Redis: {e}")
            return False # Critical failure

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
        try:
            self.redis.publish('openclaw:cluster:failover', json.dumps(failover_event))
        except redis_exceptions.RedisError as e:
            print(f"[FailoverManager] WARNING: Failed to publish failover event for {failed_node}: {e}")
    
    def _migrate_sessions(self, from_node: str) -> int:
        """Migrate active sessions from failed node"""
        # Find sessions owned by failed node
        pattern = f'openclaw:cluster:sessions:*'
        migrated = 0
        
        try:
            for key in self.redis.scan_iter(match=pattern):
                try:
                    session_data = self.redis.get(key)
                except redis_exceptions.RedisError as e:
                    print(f"[FailoverManager] WARNING: Failed to get session data for key {key}: {e}")
                    continue # Skip this session

                if session_data:
                    try:
                        session = json.loads(session_data)
                    except json.JSONDecodeError as e:
                        print(f"[FailoverManager] WARNING: Failed to decode session data for key {key}: {e}. Skipping migration for this session.")
                        continue # Skip this session

                    if session.get('node_id') == from_node:
                        session['node_id'] = 'migrating'
                        session['migrated_from'] = from_node
                        session['migrated_at'] = time.time()
                        try:
                            self.redis.setex(key, 3600, json.dumps(session))
                            migrated += 1
                        except redis_exceptions.RedisError as e:
                            print(f"[FailoverManager] WARNING: Failed to setex session {key} during migration: {e}")

        except redis_exceptions.RedisError as e:
            print(f"[FailoverManager] ERROR: Failed to scan Redis for sessions during migration from {from_node}: {e}")
        
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
