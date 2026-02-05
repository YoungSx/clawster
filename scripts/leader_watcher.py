#!/usr/bin/env python3
"""
OpenClaw Distributed - Leader Watcher
Leader 选举守护进程，定期竞争/续约 Leader 位置

工作流程:
1. 定期检查当前 Leader 状态
2. 如果没有 Leader，尝试竞选
3. 如果当前是 Leader，按时续约锁
4. 监控 Leader 变更事件
"""

import json
import time
import sys
import os
from typing import Optional, Dict, Any
from pathlib import Path

# 添加脚本目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from redis_client import RedisClient
from leader_election import LeaderElection
from config_loader import get_redis_config, get_node_config


class LeaderWatcher:
    """
    Leader 选举监控守护进程
    """

    def __init__(self,
                 node_id: Optional[str] = None,
                 redis_config: Optional[Dict[str, Any]] = None,
                 lock_ttl: int = 60,
                 check_interval: float = 10.0,
                 renew_threshold: float = 0.5):
        """
        初始化 Leader Watcher

        Args:
            node_id: 节点 ID，默认自动生成
            redis_config: Redis 连接配置
            lock_ttl: 锁 TTL (秒)
            check_interval: 检查间隔 (秒)，默认 10 秒
            renew_threshold: 续约阈值 (TTL 剩余比例)，默认 50% 时续约
        """
        self.node_id = node_id
        self.redis_config = redis_config or self._load_redis_config()
        
        # 先加载配置
        config = self._load_config()
        
        # 优先使用传入值，未传入则从配置读取
        if lock_ttl is None:
            # 使用专门的 leader_ttl 配置，默认 60 秒
            self.lock_ttl = config.get('node', {}).get('leader_ttl') or config.get('election', {}).get('lock_ttl', 60)
            print(f"[LeaderWatcher] ℹ️ lock_ttl 从配置读取: {self.lock_ttl}")
        else:
            self.lock_ttl = lock_ttl
            
        if check_interval is None:
            interval_ms = config.get('cluster', {}).get('heartbeat', {}).get('interval_ms', 5000)
            self.check_interval = interval_ms / 1000.0
        else:
            self.check_interval = check_interval
            
        # renew_threshold 从配置读取
        if renew_threshold is None:
            self.renew_threshold = config.get('election', {}).get('renew_threshold', 0.83)
            print(f"[LeaderWatcher] ℹ️ renew_threshold 从配置读取: {self.renew_threshold}")
        else:
            self.renew_threshold = renew_threshold

        # 初始化 LeaderElection
        # 注意：auto_release=False 防止 --once 模式下自动释放锁
        self.election = LeaderElection(
            node_id=self.node_id,
            redis_config=self.redis_config,
            lock_ttl=lock_ttl,
            auto_release=False
        )

        self.node_id = self.election.node_id
        self._running = False

    def _load_config(self) -> Dict[str, Any]:
        """从配置文件加载 Leader 选举配置"""
        config_paths = [
            Path(__file__).parent.parent / 'config' / 'config.json',
            Path(__file__).parent.parent / 'config.json',
            Path('/home/shangxin/clawd/clawster/config/config.json'),
        ]
        for path in config_paths:
            if path.exists():
                with open(path) as f:
                    return json.load(f)
        return {}

    def _load_redis_config(self) -> Dict[str, Any]:
        """使用统一配置加载器获取 Redis 配置"""
        redis_cfg = get_redis_config()
        redis_cfg['socket_timeout'] = 5.0
        return redis_cfg

    def _should_renew(self) -> bool:
        """判断是否应该续约"""
        ttl = self.election.get_ttl()
        # TTL 小于阈值比例时续约 (默认 50%)
        threshold_seconds = self.lock_ttl * self.renew_threshold
        return ttl < threshold_seconds

    def run_once(self) -> bool:
        """
        执行一次 Leader 选举逻辑

        Returns:
            bool: 当前是否为 Leader
        """
        if self.election.is_leader():
            # 当前是 Leader，检查是否需要续约
            if self._should_renew():
                success = self.election.renew_leadership()
                if success:
                    print(f"[LeaderWatcher] ✅ 续约成功 | node={self.node_id} | ttl={self.election.get_ttl()}s")
                else:
                    print(f"[LeaderWatcher] ❌ 续约失败，失去 Leadership | node={self.node_id}")
                    # 尝试重新竞选
                    return self._try_elect()
            return True
        else:
            # 不是 Leader，尝试竞选
            return self._try_elect()

    def _try_elect(self) -> bool:
        """尝试竞选 Leader"""
        current_leader = self.election.get_current_leader()
        
        if current_leader:
            # 有 Leader，检查是否存活
            ttl = self.election.get_ttl()
            if ttl > 0:
                print(f"[LeaderWatcher] ℹ️ 当前 Leader: {current_leader} (TTL: {ttl}s)，保持 Follower 状态")
                return False
            else:
                print(f"[LeaderWatcher] ⚠️ Leader 锁已过期，尝试竞选...")
        else:
            print(f"[LeaderWatcher] ℹ️ 无 Leader，尝试竞选...")

        # 尝试获取锁
        success = self.election.try_acquire_leadership()
        if success:
            print(f"[LeaderWatcher] 🎉 竞选成功！节点 {self.node_id} 成为 Leader")
        else:
            # 竞选失败，可能其他节点抢先了
            new_leader = self.election.get_current_leader()
            if new_leader:
                print(f"[LeaderWatcher] ℹ️ 竞选失败，当前 Leader: {new_leader}")
            else:
                print(f"[LeaderWatcher] ℹ️ 竞选失败，稍后重试")

        return success

    def watch(self, duration_seconds: Optional[float] = None):
        """
        持续监控 Leader 状态

        Args:
            duration_seconds: 运行时长 (秒)，None 表示永久运行
        """
        self._running = True
        start_time = time.time()

        print(f"[LeaderWatcher] 🚀 启动 Leader Watcher | node={self.node_id} | interval={self.check_interval}s")

        while self._running:
            try:
                self.run_once()

                # 检查运行时长
                if duration_seconds and (time.time() - start_time) >= duration_seconds:
                    print(f"[LeaderWatcher] ⏹️ 达到运行时长，停止监控")
                    break

                # 等待下一次检查
                time.sleep(self.check_interval)

            except KeyboardInterrupt:
                print(f"[LeaderWatcher] ⏹️ 收到中断信号，停止监控")
                break
            except Exception as e:
                print(f"[LeaderWatcher] ❌ 运行出错: {e}")
                time.sleep(self.check_interval)

        # 清理
        self.stop()

    def stop(self):
        """停止监控并释放资源"""
        self._running = False
        if self.election.is_leader():
            self.election.release_leadership()
            print(f"[LeaderWatcher] 👋 已主动释放 Leadership")

    def get_status(self) -> Dict[str, Any]:
        """获取当前状态"""
        return {
            'node_id': self.node_id,
            'is_leader': self.election.is_leader(),
            'current_leader': self.election.get_current_leader(),
            'lock_ttl': self.lock_ttl,
            'ttl_remaining': self.election.get_ttl(),
        }


def main():
    """CLI 入口"""
    import argparse

    parser = argparse.ArgumentParser(description='Leader 选举监控守护进程')
    parser.add_argument('--node-id', help='节点 ID')
    parser.add_argument('--interval', type=float, default=None, help='检查间隔 (秒)，默认从配置读取')
    parser.add_argument('--ttl', type=int, default=None, help='锁 TTL (秒)，默认从配置读取')
    parser.add_argument('--once', action='store_true', help='运行一次后退出')
    parser.add_argument('--duration', type=float, help='运行时长 (秒)')

    args = parser.parse_args()

    watcher = LeaderWatcher(
        node_id=args.node_id,
        check_interval=args.interval,
        lock_ttl=args.ttl
    )

    if args.once:
        is_leader = watcher.run_once()
        print(json.dumps(watcher.get_status(), indent=2))
        sys.exit(0 if is_leader else 1)
    else:
        watcher.watch(duration_seconds=args.duration)


if __name__ == '__main__':
    main()
