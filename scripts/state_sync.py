#!/usr/bin/env python3
"""OpenClaw Distributed - State Sync

Handles state synchronization across cluster nodes.
Lightweight event publishing/subscribing via Redis streams.
"""

import json
import time
import threading
from typing import Dict, Any, Optional, Callable

try:
    from .redis_client import RedisClient
except ImportError:
    from redis_client import RedisClient


class StateSync:
    """Manages state synchronization across the cluster."""
    
    def __init__(self, node_id: str, redis_host: str, redis_port: int = 6379, 
                 redis_password: str = None, redis_db: int = 0):
        self.node_id = node_id
        self.redis = RedisClient(
            host=redis_host,
            port=redis_port,
            password=redis_password,
            db=redis_db
        )
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._handlers: Dict[str, Callable] = {}
    
    def start(self):
        """Start the state sync service."""
        self._running = True
        self._thread = threading.Thread(target=self._poll_events, daemon=True)
        self._thread.start()
    
    def stop(self):
        """Stop the state sync service."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
    
    def publish_event(self, event_type: str, key: str, value: dict):
        """Publish an event to the cluster stream."""
        event = {
            'node_id': self.node_id,
            'type': event_type,
            'key': key,
            'value': value,
            'timestamp': time.time()
        }
        event_json = json.dumps(event)
        # Use Redis list as simple queue if streams not available
        self.redis._cmd(['LPUSH', 'openclaw:cluster:events', event_json])
        self.redis._cmd(['LTRIM', 'openclaw:cluster:events', '0', '9999'])
    
    def register_handler(self, event_type: str, handler: Callable):
        """Register a handler for event types."""
        self._handlers[event_type] = handler
    
    def _poll_events(self):
        """Poll for events from other nodes."""
        while self._running:
            try:
                # Use BRPOP for blocking pop with timeout
                result = self.redis._cmd(['BRPOP', 'openclaw:cluster:events', '1'])
                if result and len(result) >= 2:
                    event_json = result[1]
                    event = json.loads(event_json)
                    
                    # Ignore our own events
                    if event.get('node_id') == self.node_id:
                        continue
                    
                    # Dispatch to handler
                    event_type = event.get('type')
                    if event_type in self._handlers:
                        try:
                            self._handlers[event_type](event)
                        except Exception as e:
                            print(f"[StateSync] Handler error: {e}")
            except Exception as e:
                print(f"[StateSync] Poll error: {e}")
                time.sleep(1.0)
