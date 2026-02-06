"""Gossip protocol for distributed agent coordination.

Integrates:
- SchemaValidator: validate messages at boundaries
- MemoryDecayFilter: prioritize high-relevance gossip
- ProvenanceTracker: verify capability chains
"""
import asyncio
import json
import random
from datetime import datetime
from typing import Dict, List, Set, Any, Optional

from ..schemas.validator import SchemaValidator
from ..schemas.vector_clock import VectorClock
from ..memory.decay import MemoryDecayFilter
from .provenance import ProvenanceTracker


class GossipMessage:
    """Standard gossip message format."""
    
    def __init__(self, 
                 node_id: str,
                 message_type: str,  # 'heartbeat', 'state', 'capability', 'alert'
                 payload: Dict[str, Any],
                 vector_clock: Optional[Dict] = None):
        self.node_id = node_id
        self.type = message_type
        self.payload = payload
        self.vector_clock = vector_clock or {node_id: 1}
        self.timestamp = datetime.utcnow().isoformat()
    
    def to_dict(self) -> Dict:
        return {
            "node_id": self.node_id,
            "type": self.type,
            "payload": self.payload,
            "vector_clock": self.vector_clock,
            "timestamp": self.timestamp
        }


class GossipProtocol:
    """
    Epidemic gossip protocol with schema validation and memory filtering.
    
    Design choices:
    - Push-based gossip (our node initiates)
    - Mesh topology (random fanout)
    - TTL-based termination
    - Vector clock for causality
    """
    
    def __init__(self, node_id: str, fanout: int = 3, ttl: int = 3):
        self.node_id = node_id
        self.fanout = fanout
        self.ttl = ttl
        
        # Integrations
        self.validator = SchemaValidator()
        self.vector_clock = VectorClock(node_id)
        self.memory_filter = MemoryDecayFilter()
        self.provenance = ProvenanceTracker(node_id)
        
        # Gossip state
        self._known_nodes: Set[str] = set()
        self._seen_messages: Set[str] = set()
        self._message_queue: asyncio.Queue = asyncio.Queue()
    
    def register_node(self, node_id: str):
        """Add node to gossip mesh."""
        self._known_nodes.add(node_id)
    
    def create_gossip(self, message_type: str, payload: Dict) -> Optional[GossipMessage]:
        """
        Create validated gossip message.
        
        Returns None if validation fails.
        """
        # Validate schema
        temp_msg = {
            "node_id": self.node_id,
            "timestamp": datetime.utcnow().isoformat(),
            "output_type": "gossip",
            "payload": payload,
            "version": "0.2.0",
            "vector_clock": self.vector_clock.to_dict()
        }
        
        is_valid, error = self.validator.validate_node_output(temp_msg)
        if not is_valid:
            return None
        
        # Increment vector clock
        self.vector_clock.increment()
        
        return GossipMessage(
            node_id=self.node_id,
            message_type=message_type,
            payload=payload,
            vector_clock=self.vector_clock.to_dict()
        )
    
    async def gossip_loop(self, gossip_func, interval: float = 30.0):
        """
        Main gossip loop.
        
        Args:
            gossip_func: Async function to send gossip to peer
            interval: Seconds between gossip rounds
        """
        while True:
            await self._gossip_round(gossip_func)
            await asyncio.sleep(interval)
    
    async def _gossip_round(self, gossip_func):
        """Single gossip round: select targets and push."""
        if len(self._known_nodes) < self.fanout:
            return
        
        # Select random fanout targets
        targets = random.sample(list(self._known_nodes), self.fanout)
        
        # Collect high-relevance messages
        keep, _ = self.memory_filter.filter_by_relevance()
        messages = [self.memory_filter.get_checkpoint_data(mid) 
                   for mid in keep[:5]]  # Top 5
        
        # Create gossip
        gossip = self.create_gossip("state", {
            "messages": messages,
            "known_nodes": list(self._known_nodes)
        })
        
        if not gossip:
            return
        
        # Push to targets
        tasks = [gossip_func(target, gossip.to_dict()) for target in targets]
        await asyncio.gather(*tasks, return_exceptions=True)
    
    def receive_gossip(self, message: Dict) -> tuple[bool, str]:
        """
        Process received gossip.
        
        Returns: (accepted, reason)
        """
        # Validate
        is_valid, error = self.validator.validate_node_output(message)
        if not is_valid:
            return False, f"Invalid: {error}"
        
        # Vector clock check
        other_vc = message.get("vector_clock", {})
        result = self.vector_clock.compare(VectorClock(message["node_id"], other_vc))
        
        if result == "concurrent":
            # Merge clocks
            self.vector_clock = self.vector_clock.merge(
                VectorClock(message["node_id"], other_vc)
            )
        elif result == "before":
            # Stale message
            return False, "Stale (before our state)"
        
        # Deduplicate
        msg_hash = hash(json.dumps(message, sort_keys=True))
        if msg_hash in self._seen_messages:
            return False, "Duplicate"
        
        self._seen_messages.add(msg_hash)
        
        # Extract and filter content
        payload = message.get("payload", {})
        for msg_data in payload.get("messages", []):
            if msg_data and msg_data.get("relevance_score", 0) > 0.5:
                # High value - add to memory
                mid = f"gossip_{hash(msg_data['content']) % 10000}"
                self.memory_filter.add(mid, msg_data["content"])
        
        # Update known nodes
        for node in payload.get("known_nodes", []):
            self._known_nodes.add(node)
        
        return True, "Accepted"
    
    def attest_capability(self, capability: str, stake: float = 0.0) -> Dict:
        """Attest to a capability with provenance."""
        entry = self.provenance.attest(capability, self.node_id, stake)
        self.provenance.add_to_chain(capability, entry)
        return {
            "capability": capability,
            "chain": self.provenance.get_chain(capability)
        }
    
    def verify_peer_capability(self, capability: str, 
                               chain: List[Dict]) -> tuple[bool, str]:
        """Verify capability provenance from peer."""
        # Load chain
        for entry_data in chain:
            from .provenance import ProvenanceEntry
            entry = ProvenanceEntry(**entry_data)
            self.provenance.add_to_chain(capability, entry)
        
        # Verify
        return self.provenance.verify_chain(capability)
