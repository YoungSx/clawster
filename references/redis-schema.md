# Redis Schema for OpenClaw Distributed

Complete documentation of all Redis keys used for cluster coordination.

## Key Prefixes

All keys use the prefix: `openclaw:cluster:`

---

## Node Registry

### Key: `openclaw:cluster:nodes`
**Type**: Hash  
**TTL**: Persistent  
**Description**: Registry of all nodes in the cluster

**Value Format**:
```json
{
  "node_id": {
    "node_id": "node-001",
    "node_name": "oci-primary",
    "state": "leader",
    "term": 5,
    "registered_at": "2026-02-01T20:00:00Z",
    "last_seen": "2026-02-01T21:30:00Z",
    "capabilities": ["gateway", "models"],
    "endpoint": "ws://192.168.1.10:18789"
  }
}
```

**Redis Commands**:
```bash
# Register node
HSET openclaw:cluster:nodes node-001 '{...}'

# Get all nodes
HGETALL openclaw:cluster:nodes

# Get specific node
HGET openclaw:cluster:nodes node-001

# Remove node
HDEL openclaw:cluster:nodes node-001
```

---

## Heartbeat

### Key: `openclaw:cluster:heartbeat:{node_id}`
**Type**: String  
**TTL**: 30 seconds (2x heartbeat timeout)  
**Description**: Node health status

**Value Format**:
```json
{
  "timestamp": 1738440000.123,
  "state": "leader",
  "term": 5,
  "leader": "node-001",
  "uptime": 3600
}
```

**Redis Commands**:
```bash
# Send heartbeat (30s TTL)
SETEX openclaw:cluster:heartbeat:node-001 30 '{...}'

# Check heartbeat
GET openclaw:cluster:heartbeat:node-001
```

---

## Leader Election

### Key: `openclaw:cluster:leader`
**Type**: String  
**TTL**: Persistent  
**Description**: Current leader node info

**Value Format**:
```json
{
  "node_id": "node-001",
  "term": 5,
  "elected_at": 1738440000
}
```

### Key: `openclaw:cluster:leader:lock`
**Type**: String  
**TTL**: 30 seconds  
**Description**: Distributed lock for leader

**Value Format**:
```
node-001:5
```

**Redis Commands**:
```bash
# Try acquire leadership
SET openclaw:cluster:leader:lock "node-001:5" NX EX 30

# Check who holds lock
GET openclaw:cluster:leader:lock

# Release lock
DEL openclaw:cluster:leader:lock
```

---

## Event Stream

### Key: `openclaw:cluster:events`
**Type**: Stream  
**TTL**: Auto-trim after 1000 entries  
**Description**: Cluster event log

**Event Types**:
- `node_joined`
- `node_left`
- `node_failed`
- `node_recovered`
- `election_started`
- `leader_elected`
- `failover_triggered`

**Value Format**:
```json
{
  "timestamp": "1738440000.123",
  "node_id": "node-001",
  "event": "node_failed",
  "reason": "heartbeat_timeout"
}
```

**Redis Commands**:
```bash
# Add event
XADD openclaw:cluster:events * event node_failed node_id node-001

# Read events
XREAD STREAMS openclaw:cluster:events 0

# Read with range
XRANGE openclaw:cluster:events - +

# Trim to 1000 entries
XTRIM openclaw:cluster:events MAXLEN 1000
```

---

## Session Cache

### Key: `openclaw:cluster:sessions:{session_id}`
**Type**: String  
**TTL**: 24 hours  
**Description**: Distributed session cache

**Value Format**:
```json
{
  "session_id": "agent:main:telegram:95908897",
  "node_id": "node-001",
  "user_id": "95908897",
  "channel": "telegram",
  "created_at": 1738440000,
  "last_activity": 1738443600,
  "context": "..."
}
```

**Redis Commands**:
```bash
# Store session
SETEX openclaw:cluster:sessions:agent:main:telegram:95908897 86400 '{...}'

# Get session
GET openclaw:cluster:sessions:agent:main:telegram:95908897

# Find all sessions
KEYS openclaw:cluster:sessions:*
```

---

## Memory Synchronization

### Key: `openclaw:cluster:memory:stream`
**Type**: Stream  
**TTL**: Auto-trim after 10000 entries  
**Description**: Memory file changes stream

**Value Format**:
```json
{
  "timestamp": 1738440000,
  "node_id": "node-001",
  "file": "memory/2026-02-01.md",
  "action": "append",
  "content_hash": "abc123",
  "content_preview": "..."
}
```

### Key: `openclaw:cluster:memory:versions:{file_path}`
**Type**: String  
**TTL**: 30 days  
**Description**: Latest version tracking for memory files

**Value Format**:
```json
{
  "version": 42,
  "hash": "sha256:abc123",
  "updated_at": 1738440000,
  "updated_by": "node-001"
}
```

---

## Failover

### Key: `openclaw:cluster:failover:active`
**Type**: Hash  
**TTL**: 1 hour  
**Description**: Active failover operations

**Value Format**:
```json
{
  "failed_node": "node-002",
  "detected_at": 1738440000,
  "action": "sessions_migrated",
  "new_leader": "node-001",
  "status": "in_progress"
}
```

---

## Voting (Leader Election)

### Key: `openclaw:cluster:votes:{term}:{voter_node}`
**Type**: String  
**TTL**: 10 seconds  
**Description**: Vote record for leader election

**Value Format**:
```
node-001
```

---

## Pub/Sub Channels

### Channel: `openclaw:cluster:failover`
**Purpose**: Notify nodes of failover events

**Message Format**:
```json
{
  "type": "failover",
  "failed_node": "node-002",
  "timestamp": 1738440000,
  "action": "sessions_migrated"
}
```

### Channel: `openclaw:cluster:state`
**Purpose**: State change notifications

**Message Format**:
```json
{
  "type": "leader_change",
  "old_leader": "node-001",
  "new_leader": "node-002",
  "term": 6
}
```

---

## Complete Redis Query Examples

```bash
# Get cluster summary
redis-cli \
  EVAL "local nodes = redis.call('hgetall', 'openclaw:cluster:nodes'); return nodes" 0

# List active leader
redis-cli GET openclaw:cluster:leader

# Recent events (last 10)
redis-cli XREVRANGE openclaw:cluster:events + - COUNT 10

# All failed nodes
redis-cli EVAL "
  local nodes = redis.call('hgetall', 'openclaw:cluster:nodes');
  local failed = {};
  for i=1,#nodes,2 do
    local info = cjson.decode(nodes[i+1]);
    if info.state == 'failed' then
      table.insert(failed, nodes[i]);
    end
  end
  return failed;
" 0
```
