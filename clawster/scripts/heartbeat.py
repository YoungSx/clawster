#!/usr/bin/env python3
"""
Safe heartbeat - loads credentials from env file, no hardcoding.
"""
import sys
import json
import time
import os
from datetime import datetime
from pathlib import Path

# Load from .env if exists (gitignored)
ENV_FILE = Path('/home/shangxin/clawd/.env')
if ENV_FILE.exists():
    with open(ENV_FILE) as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                key, val = line.strip().split('=', 1)
                os.environ[key] = val

def send_heartbeat(node_id='RouterLadderbot', ttl=30):
    try:
        import redis
        
        # Load from env (set by .env or parent process)
        host = os.getenv('REDIS_HOST')
        port = int(os.getenv('REDIS_PORT', '11877'))
        password = os.getenv('REDIS_PASSWORD')
        
        if not host or not password:
            print("❌ REDIS_HOST or REDIS_PASSWORD not set", file=sys.stderr)
            return False
        
        r = redis.Redis(
            host=host, port=port, password=password, db=0,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5
        )
        
        hb_data = json.dumps({
            "node": node_id,
            "status": "online",
            "role": "leader",
            "ts": datetime.utcnow().isoformat(),
            "version": "0.2.0"
        })
        
        r.setex(f"hb:{node_id}", ttl, hb_data)
        r.zadd("openclaw:cluster:nodes", {node_id: time.time()})
        
        print(f"✅ {datetime.utcnow().isoformat()} heartbeat OK")
        return True
        
    except Exception as e:
        print(f"❌ {e}", file=sys.stderr)
        return False

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--node-id', default='RouterLadderbot')
    args = parser.parse_args()
    
    success = send_heartbeat(args.node_id)
    sys.exit(0 if success else 1)
