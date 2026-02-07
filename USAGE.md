# Clawster Usage Guide

## Quick Start

### 1. Setup Environment

```bash
# Create .env file
cat > .secrets/config.env << 'EOF'
REDIS_HOST=your_redis_host
REDIS_PORT=6379
REDIS_PASSWORD=your_password
EOF

# Verify
cd clawster && python3 scripts/heartbeat.py --once
```

### 2. Run Heartbeat

```bash
# Manual run
python3 clawster/scripts/heartbeat.py --node-id RouterLadderbot

# With systemd/cron
*/1 * * * * cd /home/shangxin/clawd && python3 clawster/scripts/heartbeat.py --once
```

### 3. Use Gossip Protocol

```python
from clawster.protocol.gossip import GossipProtocol

# Create node
gp = GossipProtocol("my_node", fanout=3)

# Register peers
gp.register_node("peer_1")
gp.register_node("peer_2")

# Create gossip
msg = gp.create_gossip("state", {"data": "value"})

# Attest capability
result = gp.attest_capability("my_skill", stake=100)
```

### 4. Vector Clock Usage

```python
from clawster.schemas.vector_clock import VectorClock

vc1 = VectorClock("node_a")
vc1.increment().increment()

vc2 = VectorClock("node_b", {"node_b": 1})

# Compare
result = vc1.compare(vc2)  # "before", "after", "concurrent"
print(result)
```

## Testing

```bash
cd /home/shangxin/clawd
python3 tests/integration/test_gossip_protocol.py
```

## More Examples

See `examples/` directory for complete usage examples.
