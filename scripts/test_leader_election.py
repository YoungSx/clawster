#!/usr/bin/env python3
"""
OpenClaw Distributed - Leader Election 测试脚本 (兼容版)
移除 Emoji 以防止 Windows GBK 环境下的编码崩溃。
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
from config_loader import get_redis_config


def load_redis_config() -> Dict[str, Any]:
    """使用统一配置加载器获取 Redis 配置"""
    cfg = get_redis_config()
    cfg['socket_timeout'] = 5.0
    return cfg


def test_single_node():
    """单节点测试：获取 Leader，续约，释放"""
    print("\n" + "=" * 60)
    print("TEST: Single Node Leader Election")
    print("=" * 60)

    redis_config = load_redis_config()
    node_id = "test-node-1"

    print(f"\n1. Create node: {node_id}")
    election = LeaderElection(node_id=node_id, redis_config=redis_config, lock_ttl=10)

    # 尝试获取 Leader
    print("\n2. Try acquire leadership...")
    success = election.try_acquire_leadership()
    print(f"   Result: {'SUCCESS' if success else 'FAILED'}")

    if success:
        print(f"   Is Leader: {election.is_leader()}")
        print(f"   Lock TTL: {election.get_ttl()}s")
        print(f"   Current Leader ID: {election.get_current_leader()}")

        # 模拟续约
        print("\n3. Wait 3s then renew...")
        time.sleep(3)
        renewed = election.renew_leadership()
        print(f"   Renew Result: {'SUCCESS' if renewed else 'FAILED'}")
        print(f"   New TTL: {election.get_ttl()}s")

        # 查询信息
        print("\n4. Query Info:")
        info = election.get_info()
        for key, value in info.items():
            print(f"   {key}: {value}")

        # 释放锁
        print("\n5. Release leadership...")
        released = election.release_leadership()
        print(f"   Release Result: {'SUCCESS' if released else 'FAILED'}")
        print(f"   Is Leader: {election.is_leader()}")

    print("\n[PASS] Single node test completed!")


def test_multi_node(num_nodes: int = 3, duration: float = 10.0):
    """多节点并发测试"""
    print("\n" + "=" * 60)
    print(f"TEST: Multi-node Concurrency ({num_nodes} nodes, {duration}s)")
    print("=" * 60)

    redis_config = load_redis_config()
    results: Dict[str, List[str]] = {f"node-{i}": [] for i in range(num_nodes)}
    stop_event = threading.Event()

    def node_worker(node_id: str, results: Dict):
        election = LeaderElection(node_id=node_id, redis_config=redis_config, lock_ttl=5)
        while not stop_event.is_set():
            if not election.is_leader():
                success = election.try_acquire_leadership()
                if success:
                    results[node_id].append(f"become_leader@{time.time():.2f}")
                    print(f"[*] [{node_id}] BECAME LEADER")
            else:
                election.renew_leadership()
                results[node_id].append(f"renew@{time.time():.2f}")
            time.sleep(1)

        if election.is_leader():
            election.release_leadership()

    threads = []
    for i in range(num_nodes):
        t = threading.Thread(target=node_worker, args=(f"node-{i}", results))
        t.start()
        threads.append(t)
        time.sleep(0.2)

    time.sleep(duration)
    stop_event.set()
    for t in threads:
        t.join()

    print("\nSTATS:")
    for node_id, events in results.items():
        become_count = sum(1 for e in events if 'become' in e)
        print(f"   {node_id}: Elected {become_count} times")

    print("\n[PASS] Multi-node test completed!")


def main():
    parser = argparse.ArgumentParser(description='Leader Election Test Tool')
    parser.add_argument('--mode', choices=['single', 'multi'], default='single', help='Mode')
    args = parser.parse_args()

    if args.mode == 'single':
        test_single_node()
    else:
        test_multi_node()

    print("\n[FINISH] All tests completed!")


if __name__ == '__main__':
    main()
