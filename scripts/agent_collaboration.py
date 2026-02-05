#!/usr/bin/env python3
"""
Agent Collaboration - 1号↔2号 每小时技能交流

运行方式:
- 每小时由 cron 自动触发
- 手动运行: python3 agent_collaboration.py --node-id main-node
"""

import json
import sys
import os
import random
from datetime import datetime
from pathlib import Path
from typing import List, Dict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent_chat import AgentChat, TaskNegotiator
from redis_client import RedisClient
from config_loader import get_redis_config, get_node_config


# 交流主题轮询
TOPICS = {
    "distributed_architecture": {
        "ideas": [
            "优化 Leader 选举算法，减少网络分区影响",
            "改进心跳机制，增加自适应间隔",
            "实现故障自动转移和恢复",
            "添加分布式日志聚合",
            "优化节点发现和注册流程"
        ]
    },
    "self_evolution": {
        "ideas": [
            "创建自动技能发现机制",
            "实现工具使用效果反馈闭环",
            "改进提示词工程系统",
            "创建自动错误恢复策略",
            "设计元学习能力模块"
        ]
    },
    "memory_optimization": {
        "ideas": [
            "改进长期记忆检索算法",
            "实现上下文压缩技术",
            "创建记忆重要性评估",
            "优化跨会话记忆关联",
            "设计遗忘和归档策略"
        ]
    }
}


def load_redis_config() -> Dict:
    """使用统一配置加载器获取 Redis 配置"""
    return get_redis_config()


def load_node_config() -> Dict:
    """使用统一配置加载器获取节点配置"""
    return get_node_config()


def generate_topic_idea(hour: int) -> tuple:
    """根据小时生成交流主题"""
    # 奇数小时: 分布式架构；偶数小时: 自我进化；可被3整除: 记忆优化
    if hour % 3 == 0:
        topic_key = "memory_optimization"
    elif hour % 2 == 0:
        topic_key = "self_evolution"
    else:
        topic_key = "distributed_architecture"
    
    idea = random.choice(TOPICS[topic_key]["ideas"])
    return topic_key, idea


def generate_serialized_tasks(topic: str, idea: str) -> List[str]:
    """为想法生成满载的子代理任务（5-10个）"""
    tasks = {
        "distributed_architecture": [
            f"调研现有{idea}的最佳实践方案",
            f"设计{idea}的架构图和流程图",
            f"编写{idea}的核心代码实现",
            f"实现{idea}的单元测试和集成测试",
            f"创建{idea}的性能基准测试",
            f"编写{idea}的技术文档",
            f"实现{idea}的监控和告警",
            f"进行{idea}的故障注入测试",
            f"优化{idea}的资源使用效率",
            f"撰写{idea}的部署和运维指南"
        ],
        "self_evolution": [
            f"研究{idea}的相关学术论文",
            f"调研开源社区关于{idea}的实现",
            f"设计{idea}的实验验证方案",
            f"实现{idea}的原型代码",
            f"收集{idea}的效果数据",
            f"分析{idea}的成功率和失败模式",
            f"优化{idea}的执行效率",
            f"创建{idea}的自动化流程",
            f"编写{idea}的使用指南",
            f"分享{idea}的实践经验"
        ],
        "memory_optimization": [
            f"分析当前{idea}的瓶颈",
            f"调研{idea}的现有算法实现",
            f"设计{idea}的新算法架构",
            f"实现{idea}的核心代码",
            f"测试{idea}的准确性和召回率",
            f"优化{idea}的存储效率",
            f"实现{idea}的批量处理",
            f"创建{idea}的A/B测试方案",
            f"分析{idea}的效果指标",
            f"总结{idea}的改进建议"
        ]
    }
    
    base_tasks = tasks.get(topic, tasks["self_evolution"])
    # 随机选择5-10个任务
    num_tasks = random.randint(5, 10)
    return random.sample(base_tasks, min(num_tasks, len(base_tasks)))

def check_workload(redis_config: Dict, partner: str) -> tuple:
    """检查当前工作量，返回(是否有工作, 工作饱和度 0-1, 建议主题)"""
    client = RedisClient(**redis_config)
    client.connect()
    
    workload_score = 0.0
    reasons = []
    
    # 1. 检查集群节点活跃度
    nodes = client.hgetall('openclaw:cluster:nodes')
    online_nodes = 0
    for node_id in nodes:
        hb = client.get(f'hb:{node_id}')
        if hb:
            import time
            hb_data = json.loads(hb)
            age = time.time() - hb_data['timestamp']
            if age < 60:
                online_nodes += 1
    
    if online_nodes <= 1:
        workload_score += 0.3
        reasons.append(f"在线节点少({online_nodes}个)")
    
    # 2. 检查待处理消息
    partner_msgs = client.llen(f'openclaw:chat:{partner}')
    if partner_msgs < 2:
        workload_score += 0.3
        reasons.append(f"伙伴消息少({partner_msgs}条)")
    
    # 3. 检查最近任务历史
    history = client.lrange(f'openclaw:chat:history:{partner}', 0, 4)
    if len(history) < 3:
        workload_score += 0.2
        reasons.append("近期任务交流少")
    
    # 4. 检查Leader状态
    leader = client.get('openclaw:cluster:leader_lock')
    if not leader:
        workload_score += 0.2
        reasons.append("Leader选举异常")
    
    has_work = workload_score < 0.5
    suggestion = None
    
    # 如果没有工作，建议新的进化方向
    if not has_work:
        suggestions = [
            "分布式架构升级",
            "协议优化与标准化", 
            "自我改进机制设计",
            "资源调度效率提升",
            "故障自愈能力增强",
            "跨节点任务协作",
            "性能监控仪表板",
            "智能日志分析系统"
        ]
        suggestion = random.choice(suggestions)
    
    return has_work, min(workload_score, 1.0), suggestion, reasons


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Agent Collaboration')
    parser.add_argument('--node-id', required=True, help='Node ID (main-node or sx-squid-bot-follower-01)')
    parser.add_argument('--partner', default='sx-squid-bot-follower-01', help='Partner node ID')
    args = parser.parse_args()
    
    # 加载配置先
    config = load_config()
    redis_config = config['redis']
    
    # 动态发现 partner（不硬编码）
    from node_discovery import NodeRegistry
    registry = NodeRegistry(RedisClient(**redis_config), args.node_id)
    partner_info = registry.find_partner(exclude_self=True)
    partner = partner_info['node_id'] if partner_info else args.partner
    print(f"   🔍 动态发现伙伴: {partner}")
    
    print(f"\n{'='*60}")
    print(f"🤖 Agent Collaboration: {args.node_id} ↔ {partner}")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")
    
    # 初始化聊天
    chat = AgentChat(agent_id=args.node_id, redis_config=redis_config)
    negotiator = TaskNegotiator(chat)
    
    # 检查是否有对方的新消息
    unread = chat.get_unread_count()
    if unread > 0:
        print(f"📨 收到 {unread} 条来自 {partner} 的消息")
        messages = chat.get_messages(count=unread, clear=True)
        
        for msg in messages:
            print(f"\n💬 From {msg.from_agent}:")
            print(f"   Topic: {msg.topic}")
            print(f"   Content: {msg.content[:200]}...")
            
            # 如果对方提出了任务，接受并执行
            if msg.task_proposal and msg.task_proposal.get('status') == 'pending':
                print(f"\n🎯 接受任务提议！")
                negotiator.accept_and_execute(msg)
                print(f"🚀 已派出满载子代理执行任务（{msg.task_proposal.get('task_count')}个子任务）")
                return
    else:
        print(f"📭 暂无来自 {partner} 的新消息")
    
    # 检查当前工作饱和度
    print(f"\n📊 检查工作负载...")
    has_work, saturation, suggestion, reasons = check_workload(redis_config, partner)
    
    if saturation < 0.5:
        print(f"   ✅ 工作正常 (饱和度: {saturation:.0%})")
        if reasons:
            print(f"   原因: {', '.join(reasons)}")
    else:
        print(f"   🚨 工作不饱和 (饱和度: {saturation:.0%})")
        print(f"   原因: {', '.join(reasons) if reasons else '系统空闲'}")
        print(f"   💡 建议方向: {suggestion}")
    
    # 如果没有工作或系统闲置，生成新的进化工作
    if not has_work and suggestion:
        print(f"\n🔄 生成新的进化协作任务...")
        topic_key = "self_evolution"
        idea = suggestion
    else:
        # 正常轮询
        hour = datetime.now().hour
        topic_key, idea = generate_topic_idea(hour)
    
    tasks = generate_serialized_tasks(topic_key, idea)
    
    print(f"\n💡 提出新的协作想法:")
    print(f"   Topic: {topic_key}")
    print(f"   Idea: {idea}")
    print(f"   Tasks: {len(tasks)} 个子任务")
    
    # 发送任务提议
    msg = negotiator.propose_task(
        to_agent=partner,
        idea=idea,
        tasks=tasks,
        difficulty=random.randint(5, 8),
        value=random.randint(7, 9)
    )
    
    print(f"\n📤 任务提议已发送给 {partner}")
    print(f"🤝 等待对方响应...")
    print(f"\n{'='*60}\n")


if __name__ == "__main__":
    main()
