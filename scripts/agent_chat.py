#!/usr/bin/env python3
"""
Agent-to-Agent Chat Protocol via Redis
1号 ↔ 2号 技能交流协议 - Redis通信核心
"""

import json
import time
import sys
import os
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from redis_client import RedisClient


@dataclass
class AgentMessage:
    """消息格式标准（兼容1号/2号双协议）"""
    msg_id: str
    from_agent: str
    to_agent: str
    timestamp: float
    topic: Optional[str] = None
    content: Optional[str] = None
    priority: Optional[str] = None
    # 兼容2号协议：type 等价于 topic
    type: Optional[str] = None
    # 2号协议的额外字段
    my_instance: Optional[str] = None
    partner_instance: Optional[str] = None
    role: Optional[str] = None
    ready: Optional[bool] = None
    proposed_executor: Optional[str] = None
    task_proposal: Optional[Dict] = None
    
    def __post_init__(self):
        # 自动转换 type 到 topic（兼容双协议）
        if not self.topic and self.type:
            self.topic = self.type
        if not self.type and self.topic:
            self.type = self.topic
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)


class AgentChat:
    """Redis-based Agent Communication Protocol"""
    
    def __init__(self, agent_id: str, redis_config: Dict):
        self.agent_id = agent_id
        self.chat_key = f"openclaw:chat:{agent_id}"
        self.history_key = f"openclaw:chat:history:{agent_id}"
        self.redis = RedisClient(**redis_config)
        self.redis.connect()
        print(f"[AgentChat] Connected for agent: {agent_id}")
    
    def send_message(self, to_agent: str, content: str, topic: str = "general",
                     priority: str = "medium", proposed_executor: Optional[str] = None,
                     task_proposal: Optional[Dict] = None) -> AgentMessage:
        """发送消息到指定代理"""
        
        msg = AgentMessage(
            msg_id=f"{self.agent_id}:{int(time.time() * 1000)}",
            from_agent=self.agent_id,
            to_agent=to_agent,
            timestamp=time.time(),
            topic=topic,
            content=content,
            priority=priority,
            proposed_executor=proposed_executor,
            task_proposal=task_proposal
        )
        
        target_key = f"openclaw:chat:{to_agent}"
        
        # 编码为 base64 避免特殊字符问题
        import base64
        encoded = base64.b64encode(msg.to_json().encode()).decode()
        
        # 添加到对方收件箱
        self.redis.lpush(target_key, encoded)
        self.redis.ltrim(target_key, 0, 99)
        
        # 记录到自己的历史
        self.redis.lpush(self.history_key, encoded)
        self.redis.ltrim(self.history_key, 0, 999)
        
        print(f"[AgentChat] 📤 {self.agent_id} → {to_agent}: {topic}")
        return msg
    
    def get_messages(self, count: int = 10, clear: bool = False) -> List[AgentMessage]:
        """获取自己的消息"""
        import base64
        messages_raw = self.redis.lrange(self.chat_key, 0, count - 1)
        
        messages = []
        for raw in messages_raw:
            try:
                # base64 解码
                decoded = base64.b64decode(raw).decode()
                data = json.loads(decoded)
                msg = AgentMessage(**data)
                messages.append(msg)
            except Exception as e:
                print(f"[AgentChat] Parse error: {e}")
                continue
        
        if clear and messages:
            self.redis.ltrim(self.chat_key, len(messages), -1)
        
        return messages
    
    def get_latest_message(self) -> Optional[AgentMessage]:
        """获取最新消息"""
        messages = self.get_messages(count=1)
        return messages[0] if messages else None
    
    def get_unread_count(self) -> int:
        """获取未读消息数量"""
        return self.redis.llen(self.chat_key)


class TaskNegotiator:
    """任务协商逻辑"""
    
    def __init__(self, agent_chat: AgentChat):
        self.chat = agent_chat
    
    def propose_task(self, to_agent: str, idea: str, tasks: List[str],
                     difficulty: int = 5, value: int = 5) -> AgentMessage:
        """提出任务协作建议（满载子代理任务）"""
        task_proposal = {
            "idea": idea,
            "tasks": tasks,  # 5-10个子任务
            "task_count": len(tasks),
            "difficulty": difficulty,
            "value": value,
            "status": "pending"
        }
        
        content = f"【任务协作提议】\n💡 想法: {idea}\n📋 包含 {len(tasks)} 个子任务\n"
        content += f"📊 预估难度: {difficulty}/10, 价值: {value}/10\n"
        content += f"🤖 等待协商执行方..."
        
        return self.chat.send_message(
            to_agent=to_agent,
            content=content,
            topic="self_evolution",
            priority="high" if value >= 7 else "medium",
            task_proposal=task_proposal
        )
    
    def accept_and_execute(self, original_msg: AgentMessage) -> AgentMessage:
        """接受任务并标记由自己执行"""
        reply_content = f"【接受任务】\n✅ 我将执行这个包含 {original_msg.task_proposal.get('task_count', 0)} 个子任务的计划\n🚀 立即派出满载子代理！"
        
        return self.chat.send_message(
            to_agent=original_msg.from_agent,
            content=reply_content,
            topic="task_assignment",
            priority="high",
            proposed_executor=self.chat.agent_id,
            task_proposal={**original_msg.task_proposal, "status": "accepted", "executor": self.chat.agent_id}
        )


if __name__ == "__main__":
    print("Agent Chat Protocol Module Loaded")
