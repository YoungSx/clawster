# OpenClaw Distributed 架构设计原则

## 核心原则：去中心化发现

### ❌ 禁止硬编码
```python
# 错误示例
PARTNER = 'main-node'  # 永远不要这样做
if node_id == 'main-node':  # 危险！
```

### ✅ 强制动态发现
```python
# 正确做法
partner = discover_partner()  # 从注册表读取
leader = discover_leader()     # 从Leader锁读取
```

## 节点身份识别

### 1. 节点ID来源（优先级）
1. 环境变量 `OPENCLAW_NODE_ID`
2. 配置文件 `config.json` → `node.id`
3. 自动生成 `node-{uuid}`

### 2. 名字变更流程
```
改名前 → 广播RENAME_EVENT → 所有节点更新映射 → 改名后
```

### 3. 兼容机制
- 注册表保留历史名字映射
- 旧名字请求自动转发到新名字（过渡期）

## 通信协议

### 消息路由
```python
# 不依赖名字，依赖角色
if message.from_agent == current_leader():
    priority = 'high'  # Leader消息优先

# 或根据消息类型
if message.topic == 'task_assignment':
    execute()  # 不管谁发的，按内容处理
```

### 心跳检测
```python
# 遍历所有注册节点，不检查特定名字
for node_id in registry.get_all_nodes():
    check_heartbeat(node_id)  # 动态
```

## 角色与权限

### Leader选举
- 基于Redis RedLock算法
- Leader锁：`openclaw:cluster:leader_lock`
- 内容格式：`{node_id}:{timestamp}`

### Follower行为
1. 读取Leader锁确定当前Leader
2. 只向当前Leader发送状态报告
3. 接受任何节点的任务分配（不限于Leader）

## 容错设计

### 节点失联
- 心跳超时60秒视为离线
- 从注册表移除（延迟处理，避免误杀）

### Leader切换
- 旧Leader心跳过期后，新Leader竞选
- 所有节点自动识别新Leader
- 无需人工介入

## 最佳实践

### 代码规范
```python
class Node:
    def __init__(self):
        self.id = self._load_or_generate_id()  # 非硬编码
        self.partner = None  # 运行时发现
    
    def discover_partner(self):
        """每次协作前重新发现"""
        return registry.get_online_nodes(exclude=self.id)[0]
    
    def get_leader(self):
        """每次操作前检查当前Leader"""
        return leader_election.get_current_leader()
```

### 配置管理
- 节点名字：配置文件 + 环境变量覆盖
- 连接信息：secrets.json（不提交git）
- 动态参数：Redis集中存储

## 反模式警示

### ❌ 硬编码节点名
```python
# 不要这样做
send_message(to='main-node')
if partner == 'sx-squid-bot-follower-01':
```

### ❌ 假设节点存在
```python
# 危险
hb = redis.get('hb:main-node')  # 可能已改名
```

### ❌ 依赖启动顺序
```python
# 错误
if i_am_first_node():
    become_leader()  # 应该竞选举
```

## 改名事件处理

### 发起改名（1号执行）
```python
# 1. 广播事件
registry.broadcast_rename('old-name', 'new-name')

# 2. 更新自己的注册信息
registry.update_node_id('new-name')

# 3. 重新竞选Leader（如果需要）
leader_election.campaign('new-name')
```

### 接收改名（2号处理）
```python
# 在消息处理循环中
if message.type == 'RENAME_EVENT':
    # 更新本地伙伴引用
    if self.partner == message.old_name:
        self.partner = message.new_name
    # 持久化到配置
    config.update('partner', message.new_name)
```

---
**设计目标**：任何节点可以任意改名而不影响集群通信
