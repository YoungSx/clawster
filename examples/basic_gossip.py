#!/usr/bin/env python3
"""Example: Basic gossip protocol usage."""
import sys
sys.path.insert(0, '/home/shangxin/clawd')

from clawster.protocol.gossip import GossipProtocol
from clawster.protocol.provenance import ProvenanceTracker

# Create gossip node
gp = GossipProtocol(
    node_id="my_node",
    fanout=3,  # Connect to 3 peers
    ttl=3      # 3 hop TTL
)

# Register peers
gp.register_node("peer_1")
gp.register_node("peer_2")
gp.register_node("peer_3")

# Create gossip message
msg = gp.create_gossip("announcement", {
    "message": "Hello from my_node!",
    "version": "0.1.0"
})

print(f"Created gossip: {msg}")

# Attest capability with provenance
result = gp.attest_capability("gossip_protocol", stake=100)
print(f"Capability attested: {result}")

# Verify provenance
is_valid, reason = gp.provenance.verify_chain("gossip_protocol")
print(f"Provenance verification: {is_valid} ({reason})")
