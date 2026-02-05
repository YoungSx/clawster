#!/usr/bin/env python3
"""
OpenClaw Distributed - Leader Election 测试脚本
模拟多节点竞争场景，验证脑裂防护

用法:
    python3 test_leader_election.py --mode single      # 单节点测试
    python3 test_leader_election.py --mode multi       # 多节点并发测试
    python3 test_leader_election.py --mode stress      # 压力测试 (脑裂模拟)
"""

import json
import time
import sys
import os
import threading
import argparse
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from redis_client import RedisClient
from leader_election import LeaderElection
from leader_watcher import LeaderWatcher
from config_loader import get_redis_config


def load_redis_config() -> Dict[str, Any]:
    """使用统一配置加载器获取 Redis 配置"""
    cfg = get_redis_config()
    cfg['socket_timeout'] = 5.0
    return cfg


def test_single_node():
    """单节点测试：获取 Leader，续约，释放"""
    print("\n" + "=" * 60)
    print("🧪 单节点 Leader 选举测试")
    print("=" * 60)

    redis_config = load_redis_config()
    node_id = "test-node-1"

    print(f"\n1. 创建节点: {node_id}")
    election = LeaderElection(node_id=node_id, redis_config=redis_config, lock_ttl=10)

    # 尝试获取 Leader
    print("\n2. 尝试获取 Leader 锁...")
    success = election.try_acquire_leadership()
    print(f"   结果: {'✅ 成功' if success else '❌ 失败'}")

    if success:
        print(f"   当前是 Leader: {election.is_leader()}")
        print(f"   Leader 锁 TTL: {election.get_ttl()}s")
        print(f"   当前 Leader ID: {election.get_current_leader()}")

        # 模拟续约
        print("\n3. 等待 3 秒后续约...")
        time.sleep(3)
        renewed = election.renew_leadership()
        print(f"   续约结果: {'✅ 成功' if renewed else '❌ 失败'}")
        print(f"   新 TTL: {election.get_ttl()}s")

        # 查询信息
        print("\n4. 查询 Leader 信息:")
        info = election.get_info()
        for key, value in info.items():
            print(f"   {key}: {value}")

        # 释放锁
        print("\n5. 主动释放 Leadership...")
        released = election.release_leadership()
        print(f"   释放结果: {'✅ 成功' if released else '❌ 失败'}")
        print(f"   当前是 Leader: {election.is_leader()}")

    print("\n✅ 单节点测试完成!")


def test_multi_node(num_nodes: int = 3, duration: float = 30.0):
    """多节点并发测试"""
    print("\n" + "=" * 60)
    print(f"🧪 多节点并发测试 ({num_nodes} 个节点, {duration}秒)")
    print("=" * 60)

    redis_config = load_redis_config()
    results: Dict[str, List[str]] = {f"node-{i}": [] for i in range(num_nodes)}
    stop_event = threading.Event()

    def node_worker(node_id: str, results: Dict):
        """节点工作线程"""
        election = LeaderElection(node_id=node_id, redis_config=redis_config, lock_ttl=15)

        while not stop_event.is_set():
            is_leader = election.is_leader()
            current_leader = election.get_current_leader()

            if not is_leader:
                # 尝试竞选
                success = election.try_acquire_leadership()
                if success:
                    results[node_id].append(f"become_leader@{time.time():.2f}")
                    print(f"🎉 [{node_id}] 成为 Leader!")
            else:
                # 续约
                election.renew_leadership()
                results[node_id].append(f"renew@{time.time():.2f}")

                # 偶尔输出状态
                if int(time.time()) % 5 == 0:
                    print(f"👑 [{node_id}] 保持 Leader, TTL={election.get_ttl()}s")

            time.sleep(2)

        # 清理
        if election.is_leader():
            election.release_leadership()

    # 启动所有节点线程
    threads = []
    for i in range(num_nodes):
        t = threading.Thread(target=node_worker, args=(f"node-{i}", results))
        t.start()
        threads.append(t)
        time.sleep(0.5)  # 错开启动时间

    # 运行指定时间
    print(f"\n⏳ 运行 {duration} 秒...\n")
    time.sleep(duration)

    # 停止
    print("\n🛑 停止所有节点...")
    stop_event.set()
    for t in threads:
        t.join()

    # 输出统计
    print("\n📊 测试结果统计:")
    for node_id, events in results.items():
        become_count = sum(1 for e in events if 'become' in e)
        renew_count = sum(1 for e in events if 'renew' in e)
        print(f"   {node_id}: 成为 Leader {become_count} 次, 续约 {renew_count} 次")

    print("\n✅ 多节点测试完成!")


def test_split_brain_simulation():
    """脑裂场景模拟测试"""
    print("\n" + "=" * 60)
    print("🧪 脑裂防护测试 (Split-Brain Protection)")
    print("=" * 60)

    redis_config = load_redis_config()

    print("\n1. 创建两个节点同时竞争...")
    node_a = LeaderElection(node_id="split-node-A", redis_config=redis_config, lock_ttl=20)
    node_b = LeaderElection(node_id="split-node-B", redis_config=redis_config, lock_ttl=20)

    # 节点 A 先获取锁
    print("\n2. 节点 A 尝试获取锁...")
    success_a = node_a.try_acquire_leadership()
    print(f"   节点 A: {'✅ 成功' if success_a else '❌ 失败'}")
    print(f"   节点 A 是 Leader: {node_a.is_leader()}")

    # 节点 B 尝试获取 (应该失败)
    print("\n3. 节点 B 尝试获取锁 (应该失败)...")
    success_b = node_b.try_acquire_leadership()
    print(f"   节点 B: {'✅ 成功' if success_b else '❌ 失败 (预期)'}")
    print(f"   节点 B 是 Leader: {node_b.is_leader()}")

    print("\n4. 验证一致性:")
    print(f"   节点 A 看到的 Leader: {node_a.get_current_leader()}")
    print(f"   节点 B 看到的 Leader: {node_b.get_current_leader()}")

    consistent = node_a.get_current_leader() == node_b.get_current_leader()
    print(f"   一致性检查: {'✅ 通过' if consistent else '❌ 失败'}")

    # 模拟节点 A 故障 (让锁过期)
    print("\n5. 模拟节点 A 故障 (等待锁过期)...")
    print(f"   当前 TTL: {node_a.get_ttl()}s")
    wait_time = 22  # 等待锁过期
    print(f"   等待 {wait_time} 秒...")
    time.sleep(wait_time)

    # 节点 B 应该能获取锁
    print("\n6. 节点 B 再次尝试获取锁...")
    success_b = node_b.try_acquire_leadership()
    print(f"   节点 B: {'✅ 成功 (预期)' if success_b else '❌ 失败'}")

    if success_b:
        print(f"   节点 B 现在是 Leader: {node_b.is_leader()}")

    # 清理
    if node_a.is_leader():
        node_a.release_leadership()
    if node_b.is_leader():
        node_b.release_leadership()

    print("\n✅ 脑裂防护测试完成!")


def main():
    parser = argparse.ArgumentParser(description='Leader Election 测试工具')
    parser.add_argument('--mode', choices=['single', 'multi', 'stress'], default='single',
                        help='测试模式')
    parser.add_argument('--nodes', type=int, default=3, help='多节点测试的节点数量')
    parser.add_argument('--duration', type=int, default=30, help='测试时长 (秒)')

    args = parser.parse_args()

    if args.mode == 'single':
        test_single_node()
    elif args.mode == 'multi':
        test_multi_node(num_nodes=args.nodes, duration=args.duration)
    elif args.mode == 'stress':
        test_split_brain_simulation()

    print("\n🏁 全部测试完成!")


if __name__ == '__main__':
    main()
