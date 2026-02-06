"""
Clawster - Distributed AI Agent System

A decentralized agent network with:
- Schema validation for node outputs
- Memory decay with configurable half-life
- Provenance tracking via isnad chains
- Vector clocks for conflict resolution
- Edge-normalized API gateway

Based on Moltbook Community Learnings
"""

__version__ = "0.2.0"
__author__ = "OpenClaw Community"

from .schemas.validator import SchemaValidator
from .memory.decay import MemoryDecayFilter
from .protocol.provenance import ProvenanceTracker
from .protocol.vector_clock import VectorClock
from .protocol.gossip import GossipProtocol

__all__ = [
    "SchemaValidator",
    "MemoryDecayFilter", 
    "ProvenanceTracker",
    "VectorClock",
    "GossipProtocol",
]
