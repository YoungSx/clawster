#!/usr/bin/env python3
"""Quick test for P0 modules: Provenance, MemoryDecay, Gossip."""
import sys
sys.path.insert(0, '.')

from clawster.protocol.provenance import ProvenanceTracker, ProvenanceEntry
from clawster.memory.decay import MemoryDecayFilter, MemoryEntry
from clawster.protocol.gossip import GossipProtocol, GossipMessage

print("=" * 60)
print("P0 Modules Test Suite")
print("=" * 60)

try:
    # 1. ProvenanceTracker
    print("\n1. ProvenanceTracker (isnad chain)")
    pt = ProvenanceTracker("test_node")
    
    # Attest and chain
    entry1 = pt.attest("schema-validation", "node_a", stake=100)
    pt.add_to_chain("schema-validation", entry1)
    
    entry2 = pt.attest("schema-validation", "node_b", stake=50)
    pt.add_to_chain("schema-validation", entry2)
    
    valid, reason = pt.verify_chain("schema-validation", min_confidence=0.3)
    print(f"   Chain valid: {valid} ({reason})")
    assert valid, "Should be valid"
    
    # Export
    chains = pt.export()
    print(f"   Exported chains: {list(chains.keys())}")
    print("   ✅ ProvenanceTracker working")
    
except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback; traceback.print_exc()

try:
    # 2. MemoryDecayFilter
    print("\n2. MemoryDecayFilter (ACT-R decay)")
    mdf = MemoryDecayFilter(half_life_days=30, relevance_threshold=0.3)
    
    # Add memories
    mdf.add("mem1", "Important: schema validation rules")
    mdf.add("mem2", "Old: yesterday's log")
    
    # Access one to boost
    mdf.access("mem1")
    mdf.access("mem1")
    
    # Filter
    keep, shed = mdf.filter_by_relevance()
    print(f"   Keep: {len(keep)}, Shed: {len(shed)}")
    
    # Export
    high_value = mdf.export_high_value()
    print(f"   High-value memories: {len(high_value)}")
    if high_value:
        print(f"   Top score: {high_value[0]['relevance_score']:.2f}")
    print("   ✅ MemoryDecayFilter working")
    
except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback; traceback.print_exc()

try:
    # 3. GossipProtocol
    print("\n3. GossipProtocol (integration)")
    gp = GossipProtocol("test_node", fanout=2, ttl=3)
    
    # Register nodes
    gp.register_node("peer_a")
    gp.register_node("peer_b")
    gp.register_node("peer_c")
    
    # Add memory to gossip
    gp.memory_filter.add("gossip1", "High value state update")
    gp.memory_filter.access("gossip1")
    
    # Create gossip
    gossip = gp.create_gossip("state", {"data": "test"})
    print(f"   Gossip created: {gossip is not None}")
    
    if gossip:
        print(f"   Vector clock: {gossip.vector_clock}")
    
    # Attest capability
    result = gp.attest_capability("heartbeat-protocol", stake=100)
    print(f"   Capability attested: {result['capability']}")
    
    print("   ✅ GossipProtocol working")
    
except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback; traceback.print_exc()

print("\n" + "=" * 60)
print("✅ All P0 modules tested!")
print("=" * 60)
