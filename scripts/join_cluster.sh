#!/bin/bash
# 一键接入1号2号集群脚本
# 用法: ./join_cluster.sh <你的节点名>

set -e

NODE_ID=${1:-"my-node-01"}
REPO_URL="https://github.com/YoungSx/clawster.git"
INSTALL_DIR="$HOME/clawster-cluster"

echo "=========================================="
echo "🚀 接入 RouterLadderbot ↔ sx_squid_bot 集群"
echo "=========================================="
echo ""

# 检查依赖
if ! command -v git &> /dev/null; then
    echo "❌ 请先安装 git"
    exit 1
fi

if ! command -v python3 &> /dev/null; then
    echo "❌ 请先安装 python3"
    exit 1
fi

# 克隆代码
echo "📦 下载集群代码..."
if [ -d "$INSTALL_DIR" ]; then
    echo "   目录已存在，执行 git pull..."
    cd "$INSTALL_DIR"
    git pull origin main
else
    git clone "$REPO_URL" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

echo "✅ 代码已就绪"
echo ""

# 配置节点名
echo "🔧 配置节点: $NODE_ID"
mkdir -p config

cat > config/config.json << EOF
{
  "node": {
    "id": "${NODE_ID}",
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
EOF

echo "✅ 节点配置已生成"
echo ""

# 提示Redis配置
echo "=========================================="
echo "⚠️  下一步: 配置Redis连接"
echo "=========================================="
echo ""
echo "请编辑: $INSTALL_DIR/config/secrets.json"
echo ""
echo "内容模板:"
echo '{'
echo '  "redis": {'
echo '    "host": "your-redis-host.redis-cloud.com",'
echo '    "port": 11877,'
echo '    "password": "your-redis-password",'
echo '    "db": 0'
echo '  }'
echo '}'
echo ""
echo "💡 你需要从集群管理员获取Redis连接信息"
echo ""

# 生成启动脚本
cat > start.sh << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"

# 检查配置
if [ ! -f "config/secrets.json" ]; then
    echo "❌ 请先配置 config/secrets.json"
    exit 1
fi

echo "🚀 启动集群节点..."
echo ""

# 启动心跳（后台）
echo "📡 启动心跳..."
while true; do
    python3 scripts/heartbeat.py 2>&1 | tee -a logs/heartbeat.log
    sleep 10
done &
HEARTBEAT_PID=$!
echo "   PID: $HEARTBEAT_PID"

# 启动Leader选举（后台）
echo "👑 启动Leader选举..."
NODE_ID=$(python3 -c "import json; print(json.load(open('config/config.json'))['node']['id'])")
while true; do
    python3 scripts/leader_watcher.py --node-id "$NODE_ID" --once 2>&1 | tee -a logs/leader.log
    sleep 10
done &
LEADER_PID=$!
echo "   PID: $LEADER_PID"

echo ""
echo "✅ 节点已启动!"
echo ""
echo "日志查看:"
echo "   tail -f logs/heartbeat.log"
echo "   tail -f logs/leader.log"
echo ""
echo "停止节点:"
echo "   kill $HEARTBEAT_PID $LEADER_PID"
echo ""

# 保存PID
echo "$HEARTBEAT_PID $LEADER_PID" > .pids

wait
EOF

chmod +x start.sh

cat > stop.sh << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"

if [ -f ".pids" ]; then
    read -r HEARTBEAT_PID LEADER_PID < .pids
    echo "🛑 停止心跳 (PID: $HEARTBEAT_PID)..."
    kill $HEARTBEAT_PID 2>/dev/null || true
    echo "🛑 停止选举 (PID: $LEADER_PID)..."
    kill $LEADER_PID 2>/dev/null || true
    rm .pids
    echo "✅ 已停止"
else
    echo "⚠️ 未找到运行中的进程"
fi
EOF

chmod +x stop.sh

# 生成测试脚本
cat > test_connection.sh << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"

echo "🔍 测试集群连接..."
echo ""

python3 << 'PYEOF'
import sys
import json
sys.path.insert(0, 'scripts')

from redis_client import RedisClient
from agent_chat import AgentChat

try:
    with open('config/secrets.json') as f:
        cfg = json.load(f)
    
    with open('config/config.json') as f:
        node_cfg = json.load(f)
    
    my_id = node_cfg['node']['id']
    
    # 测试Redis
    r = RedisClient(**cfg['redis'])
    r.connect()
    print("✅ Redis连接成功")
    
    # 检查集群状态
    leader = r.get('openclaw:cluster:leader_lock')
    print(f"👑 Leader: {leader}")
    
    nodes = r.hgetall('openclaw:cluster:nodes')
    print(f"🖥️  注册节点: {len(nodes)} 个")
    for nid in list(nodes.keys())[:5]:
        print(f"   - {nid}")
    
    # 发送测试消息给1号
    chat = AgentChat(agent_id=my_id, redis_config=cfg['redis'])
    msg = chat.send_message(
        to_agent='RouterLadderbot',
        content=f'🎉 新节点 {my_id} 测试连接成功！',
        topic='connection_test',
        priority='high'
    )
    print(f"📤 已通知 RouterLadderbot")
    
    print("\n✅ 连接测试通过！")
    
except Exception as e:
    print(f"❌ 连接失败: {e}")
    sys.exit(1)
PYEOF
EOF

chmod +x test_connection.sh

mkdir -p logs

echo "=========================================="
echo "📋 完成！下一步操作："
echo "=========================================="
echo ""
echo "1. 配置Redis连接："
echo "   vim $INSTALL_DIR/config/secrets.json"
echo ""
echo "2. 测试连接："
echo "   cd $INSTALL_DIR"
echo "   ./test_connection.sh"
echo ""
echo "3. 启动节点："
echo "   ./start.sh"
echo ""
echo "4. 查看日志："
echo "   tail -f logs/heartbeat.log"
echo ""
echo "📁 安装目录: $INSTALL_DIR"
echo "=========================================="
