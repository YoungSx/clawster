#!/usr/bin/env python3
"""
快速接入脚本 - 一键加入1号2号协作集群

使用方法:
  python3 quick_join.py
"""

import json
import os
import sys
import time
import subprocess
from pathlib import Path

def main():
    print("=" * 50)
    print("🚀 OpenClaw 集群快速接入向导")
    print("=" * 50)
    
    # 1. 获取节点名
    print("\n1. 设置你的节点名称")
    print("   建议格式: user-node-01")
    node_id = input("   输入节点ID [默认: user-node-01]: ").strip() or "user-node-01"
    
    # 2. Redis配置
    print("\n2. Redis连接配置")
    print("   请输入你的Redis连接信息（用于集群通信）")
    redis_host = input("   Host [默认: redis-11877...cloud.redislabs.com]: ").strip()
    redis_port = input("   Port [默认: 11877]: ").strip() or "11877"
    redis_pass = input("   Password: ").strip()
    
    if not redis_host:
        print("   ❌ 必须提供Redis host!")
        sys.exit(1)
    if not redis_pass:
        print("   ❌ 必须提供Redis密码!")
        sys.exit(1)
    
    # 3. 配置路径
    work_dir = Path.home() / ".openclaw" / "clawster"
    work_dir.mkdir(parents=True, exist_ok=True)
    
    # 4. 下载代码
    print(f"\n3. 下载集群代码到 {work_dir}")
    if input("   执行 git clone? [Y/n]: ").strip().lower() != 'n':
        os.chdir(work_dir.parent)
        subprocess.run([
            "git", "clone", "https://github.com/YoungSx/clawster.git"
        ], check=False)
    
    # 5. 写入配置
    print("\n4. 生成配置文件")
    config = {
        "node": {
            "id": node_id,
            "heartbeat_interval": 10,
            "heartbeat_ttl": 90,
            "retry_count": 3,
            "retry_delay": 1
        },
        "logging": {
            "level": "INFO",
            "max_bytes": 10485760,
            "backup_count": 5
        }
    }
    
    secrets = {
        "redis": {
            "host": redis_host,
            "port": int(redis_port),
            "password": redis_pass,
            "db": 0
        }
    }
    
    config_path = work_dir / "config" / "config.json"
    config_path.parent.mkdir(exist_ok=True)
    
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)
    
    secrets_path = work_dir / "config" / "secrets.json"
    with open(secrets_path, 'w') as f:
        json.dump(secrets, f, indent=2)
    
    print(f"   ✅ {config_path}")
    print(f"   ✅ {secrets_path}")
    
    # 6. 测试连接
    print("\n5. 测试Redis连接并注册节点")
    sys.path.insert(0, str(work_dir / "scripts"))
    
    try:
        from redis_client import RedisClient
        from node_discovery import NodeRegistry
        
        redis = RedisClient(**secrets['redis'])
        redis.connect()
        
        # 注册节点
        registry = NodeRegistry(redis, node_id)
        registry.register({
            'platform': 'local',
            'role': 'follower',
            'instance_id': f'{node_id}-{int(time.time())}'
        })
        
        # 发送欢迎消息
        from agent_chat import AgentChat
        chat = AgentChat(agent_id=node_id, redis_config=secrets['redis'])
        
        # 通知1号2号
        msg = chat.send_message(
            to_agent='bot_1',
            content=f'🎉 新节点加入！\\n\\n节点: {node_id}\\n平台: 本地部署\\n时间: {time.strftime("%Y-%m-%d %H:%M:%S")}',
            topic='new_node_join',
            priority='high'
        )
        
        msg2 = chat.send_message(
            to_agent='bot_2',
            content=f'🎉 新节点加入！\\n\\n节点: {node_id}\\n平台: 本地部署\\n请多指教！',
            topic='new_node_join',
            priority='high'
        )
        print(f"   ✅ 已通知 bot_1")
        print(f"   ✅ 已通知 bot_2")
        
    except Exception as e:
        print(f"   ⚠️  连接测试失败: {e}")
    
    # 7. Cron配置建议
    print("\n6. Cron定时任务配置")
    print("   在你的服务器上添加以下crontab:")
    print()
    cwd = str(work_dir)
    print(f"   # 每10秒心跳")
    print(f"   * * * * * for i in 0 1 2 3 4 5; do cd {cwd} && python3 scripts/heartbeat.py; sleep 10; done")
    print()
    print(f"   # 每10秒Leader选举")
    print(f"   * * * * * for i in 0 1 2 3 4 5; do cd {cwd} && python3 scripts/leader_watcher.py --node-id {node_id} --once; sleep 10; done")
    print()
    print(f"   # 每10分钟协作 (*/10 * * * *)")
    print(f"   */10 * * * * cd {cwd} && python3 scripts/agent_collaboration.py --node-id {node_id}")
    print()
    
    # 8. 手动启动命令
    print("7. 手动启动测试")
    print(f"   cd {cwd}")
    print(f"   python3 scripts/heartbeat.py")
    print(f"   python3 scripts/leader_watcher.py --node-id {node_id} --once")
    print(f"   python3 scripts/agent_collaboration.py --node-id {node_id}")
    print()
    
    print("=" * 50)
    print("🎉 接入完成！")
    print("=" * 50)
    print(f"\n你的节点ID: {node_id}")
    print(f"配置路径: {cwd}")
    print("\n下一步:")
    print("  1. 配置cron定时任务")
    print("  2. 运行心跳测试")
    print("  3. 等待1号2号协作邀请！")
    print()

if __name__ == '__main__':
    main()
