#!/usr/bin/env python3
"""
OpenClaw Distributed - Leader Election (RedLock Algorithm)
基于 Redis RedLock 算法的 Leader 选举实现

核心算法:
- 尝试成为 Leader: SET key value NX EX 30
- 续约: SET key value XX EX 30
- 释放: DEL key (仅当 value 匹配时)
- 检查: GET key
"""

import json
import time
import uuid
from typing import Optional, Dict, Any, Callable, List
from redis_client import RedisClient


class LeaderElection:
    """
    Leader 选举管理器 - 基于 Redis SET NX/XX 原子操作
    
    Features:
    - 分布式锁竞争 (RedLock 简化版)
    - Leader 自动续约
    - 主动释放锁
    - Leader 变更历史
    """

    LEADER_LOCK_KEY = 'openclaw:cluster:leader_lock'
    HISTORY_KEY = 'openclaw:cluster:leader_history'

    def __init__(self,
                 node_id: Optional[str] = None,
                 redis_client: Optional[RedisClient] = None,
                 redis_config: Optional[Dict[str, Any]] = None,
                 lock_ttl: int = 30,
                 auto_release: bool = True):
        self.node_id = node_id or f"node-{uuid.uuid4().hex[:8]}"
        self.lock_ttl = lock_ttl
        self._lock_value = None
        self._is_leader = False
        self._lock_acquired_at: Optional[float] = None
        self._callbacks: List[Callable] = []
        self._auto_release = auto_release

        # Redis 客户端初始化
        if redis_client:
            self.redis = redis_client
            self._owned_client = False
        elif redis_config:
            self.redis = RedisClient(**redis_config)
            self.redis.connect()
            self._owned_client = True
        else:
            raise ValueError("必须提供 redis_client 或 redis_config")

    def __del__(self):
        if self._is_leader and self._auto_release:
            self.release_leadership()
        if hasattr(self, '_owned_client') and self._owned_client:
            self.redis.close()

    # ============ 核心 RedLock 方法 ============

    def try_acquire_leadership(self) -> bool:
        """尝试获取 Leader 锁: SET key value NX EX ttl"""
        self._lock_value = f"{self.node_id}:{int(time.time() * 1000)}"
        
        try:
            result = self.redis.set(
                self.LEADER_LOCK_KEY,
                self._lock_value,
                nx=True,
                ex=self.lock_ttl
            )
            
            if result:
                self._is_leader = True
                self._lock_acquired_at = time.time()
                self._record_change('elected')
                return True
            return False
        except Exception as e:
            print(f"[LeaderElection] 获取锁失败: {e}")
            return False

    def renew_leadership(self) -> bool:
        """续约 Leader 锁: SET key value XX EX ttl"""
        if not self._is_leader:
            return False
        
        try:
            # 验证锁仍属于我们
            current = self.redis.get(self.LEADER_LOCK_KEY)
            if current != self._lock_value:
                self._lose_leadership('stolen')
                return False
            
            # 续约
            result = self.redis.set(
                self.LEADER_LOCK_KEY,
                self._lock_value,
                xx=True,
                ex=self.lock_ttl
            )
            
            if result:
                return True
            else:
                self._lose_leadership('renew_failed')
                return False
                
        except Exception as e:
            print(f"[LeaderElection] 续约失败: {e}")
            return False

    def release_leadership(self) -> bool:
        """主动释放 Leader 锁"""
        if not self._is_leader:
            return True
        
        try:
            current = self.redis.get(self.LEADER_LOCK_KEY)
            if current == self._lock_value:
                self.redis.delete(self.LEADER_LOCK_KEY)
            
            self._lose_leadership('released')
            return True
        except Exception as e:
            print(f"[LeaderElection] 释放锁失败: {e}")
            return False

    # ============ 查询方法 ============

    def _ensure_str(self, value) -> Optional[str]:
        """确保返回值是字符串类型"""
        if value is None:
            return None
        if isinstance(value, bytes):
            return value.decode('utf-8')
        return str(value)

    def get_current_leader(self) -> Optional[str]:
        """获取当前 Leader 节点 ID"""
        try:
            value = self.redis.get(self.LEADER_LOCK_KEY)
            if value:
                # Handle both str and bytes
                value_str = self._ensure_str(value)
                return value_str.split(':')[0] if value_str else None
            return None
        except Exception as e:
            print(f"[LeaderElection] get_current_leader error: {e}")
            return None

    def is_leader(self) -> bool:
        """检查当前节点是否为 Leader"""
        if self._is_leader:
            return True
        
        # --once 模式：新实例需要查询 Redis 确认是否持有锁
        try:
            current = self.redis.get(self.LEADER_LOCK_KEY)
            # Handle both str and bytes
            if isinstance(current, bytes):
                current = current.decode('utf-8')
            if current and current.startswith(f"{self.node_id}:"):
                # 锁确实属于当前节点，恢复状态
                self._lock_value = current
                self._is_leader = True
                return True
        except Exception:
            pass
        
        return False

    def get_ttl(self) -> int:
        """获取锁的剩余 TTL"""
        try:
            return self.redis.ttl(self.LEADER_LOCK_KEY)
        except:
            return -2

    def get_info(self) -> Dict[str, Any]:
        """获取详细状态"""
        return {
            'node_id': self.node_id,
            'is_leader': self._is_leader,
            'current_leader': self.get_current_leader(),
            'lock_ttl': self.lock_ttl,
            'ttl_remaining': self.get_ttl(),
            'lock_acquired_at': self._lock_acquired_at,
        }

    # ============ 内部方法 ============

    def _lose_leadership(self, reason: str):
        """失去 Leadership"""
        was_leader = self._is_leader
        self._is_leader = False
        self._lock_value = None
        self._record_change(reason)
        
        if was_leader:
            for cb in self._callbacks:
                try:
                    cb('lost', reason)
                except:
                    pass

    def _record_change(self, event: str):
        """记录 Leader 变更历史"""
        try:
            record = {
                'timestamp': time.time(),
                'node_id': self.node_id,
                'event': event,
                'is_leader': self._is_leader,
            }
            self.redis.lpush(self.HISTORY_KEY, json.dumps(record))
            self.redis.ltrim(self.HISTORY_KEY, 0, 99)  # 保留最近 100 条
        except:
            pass


if __name__ == '__main__':
    print("LeaderElection module loaded")
