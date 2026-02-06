#!/usr/bin/env python3
"""
OpenClaw Distributed - Leader Election (Atomic Version)
基于 Lua 脚本确保分布式锁的续约与释放具备原子性，防止脑裂。
"""
import json
import time
import uuid
from typing import Optional, Dict, Any, Callable, List
from redis_client import RedisClient


class LeaderElection:
    """
    Leader 选举管理器 - 基于 Redis Lua 脚本实现原子性操作
    """

    LEADER_LOCK_KEY = 'openclaw:cluster:leader_lock'
    HISTORY_KEY = 'openclaw:cluster:leader_history'

    # Lua 脚本定义
    LUA_RENEW = """
    if redis.call("GET", KEYS[1]) == ARGV[1] then
        return redis.call("PEXPIRE", KEYS[1], ARGV[2])
    else
        return 0
    end
    """

    LUA_RELEASE = """
    if redis.call("GET", KEYS[1]) == ARGV[1] then
        return redis.call("DEL", KEYS[1])
    else
        return 0
    end
    """

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

    def try_acquire_leadership(self) -> bool:
        """尝试获取 Leader 锁: SET key value NX EX ttl"""
        self._lock_value = f"{self.node_id}:{int(time.time() * 1000)}"

        try:
            # 使用统一版 RedisClient 的 SET 命令，支持 NX 和 EX
            result = self.redis.set(
                self.LEADER_LOCK_KEY,
                self._lock_value,
                nx=True,
                ex=self.lock_ttl
            )

            if result == 'OK':
                self._is_leader = True
                self._lock_acquired_at = time.time()
                self._record_change('elected')
                return True
            return False
        except Exception as e:
            print(f"[LeaderElection] 获取锁失败: {e}")
            return False

    def renew_leadership(self) -> bool:
        """使用 Lua 脚本原子续约"""
        if not self._is_leader or not self._lock_value:
            return False

        try:
            # TTL 转换为毫秒
            ttl_ms = self.lock_ttl * 1000
            result = self.redis.eval(self.LUA_RENEW, 1, self.LEADER_LOCK_KEY, self._lock_value, ttl_ms)

            if result == 1:
                return True
            else:
                self._lose_leadership('renew_failed_or_lost')
                return False
        except Exception as e:
            print(f"[LeaderElection] 续约失败: {e}")
            return False

    def release_leadership(self) -> bool:
        """使用 Lua 脚本原子释放"""
        if not self._is_leader or not self._lock_value:
            return True

        try:
            result = self.redis.eval(self.LUA_RELEASE, 1, self.LEADER_LOCK_KEY, self._lock_value)
            self._lose_leadership('released')
            return True
        except Exception as e:
            print(f"[LeaderElection] 释放锁失败: {e}")
            return False

    def get_current_leader(self) -> Optional[str]:
        """获取当前 Leader 节点 ID"""
        try:
            value = self.redis.get(self.LEADER_LOCK_KEY)
            if value:
                return value.split(':')[0]
            return None
        except Exception as e:
            print(f"[LeaderElection] get_current_leader error: {e}")
            return None

    def is_leader(self) -> bool:
        """检查当前节点是否为 Leader (含状态恢复)"""
        if self._is_leader:
            return True

        try:
            current = self.redis.get(self.LEADER_LOCK_KEY)
            if current and current.startswith(f"{self.node_id}:"):
                self._lock_value = current
                self._is_leader = True
                return True
        except:
            pass
        return False

    def _lose_leadership(self, reason: str):
        was_leader = self._is_leader
        self._is_leader = False
        self._lock_value = None
        self._record_change(reason)
        if was_leader:
            for cb in self._callbacks:
                try: cb('lost', reason)
                except: pass

    def _record_change(self, event: str):
        try:
            record = {
                'timestamp': time.time(),
                'node_id': self.node_id,
                'event': event,
                'is_leader': self._is_leader,
            }
            self.redis.lpush(self.HISTORY_KEY, json.dumps(record))
            self.redis.ltrim(self.HISTORY_KEY, 0, 99)
        except:
            pass

if __name__ == '__main__':
    print("LeaderElection module (Atomic) loaded")
