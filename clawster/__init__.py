"""
Clawster - Distributed AI Agent System

A decentralized agent network with:
- Schema validation for node outputs
- Memory decay with configurable half-life
- Provenance tracking via isnad chains
- Vector clocks for conflict resolution

Based on Moltbook Community Learnings
"""

__version__ = "0.2.0"
__author__ = "OpenClaw Community"

from .schemas.validator import SchemaValidator, ValidationError
from .schemas.vector_clock import VectorClock, VectorClockMerger

__all__ = [
    "SchemaValidator",
    "ValidationError",
    "VectorClock",
    "VectorClockMerger",
]
