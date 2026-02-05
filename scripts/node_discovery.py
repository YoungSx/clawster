#!/usr/bin/env python3
"""
Node Discovery - 节点发现与注册
提供动态节点发现和自动伙伴选择功能
"""
import json
import time
from typing import Optional, Dict, List
from pathlib import Path

class NodeRegistry:
    """节点注册表，用于动态发现集群中的节点"""
    
    def __init__(self, redis_client):
        self.redis = redis_client
        self.NODES_KEY = 'openclaw:cluster:nodes'
        self.LEADER_KEY = 'openclaw:cluster:leader_lock'
    
    def register(self, node_id: str, node_info: Dict) -> bool:
        """注册节点到集群"""
        try:
            self.redis.hset(self.NODES_KEY, node_id, json.dumps(node_info))
            return True
        except Exception as e:
            print(f"[NodeRegistry] 注册失败: {e}")
            return False
    
    def get_leader(self) -> Optional[str]:
        """获取当前Leader节点ID"""
        try:
            return self.redis.get(self.LEADER_KEY)
        except Exception:
            return None
    
    def find_partner(self, exclude_node_id: str) -> Optional[str]:
        """找到一个伙伴节点（排除自己）"""
        try:
            nodes = self.redis.hgetall(self.NODES_KEY)
            for node_id in nodes:
                if node_id != exclude_node_id:
                    # 检查心跳
                    hb = self.redis.get(f'hb:{node_id}')
                    if hb:
                        hb_data = json.loads(hb)
                        age = time.time() - hb_data['timestamp']
                        if age < 60:  # 在线
                            return node_id
            return None
        except Exception as e:
            print(f"[NodeRegistry] 查找伙伴失败: {e}")
            return None
    
    def get_online_nodes(self) -> List[str]:
        """获取所有在线节点"""
        try:
            nodes = self.redis.hgetall(self.NODES_KEY)
            online = []
            for node_id in nodes:
                hb = self.redis.get(f'hb:{node_id}')
                if hb:
                    hb_data = json.loads(hb)
                    age = time.time() - hb_data['timestamp']
                    if age < 60:
                        online.append(node_id)
            return online
        except Exception:
            return []
