"""Vector Clock implementation for distributed causal ordering."""
from typing import Dict, Optional, Tuple
from copy import deepcopy


class VectorClock:
    """
    Vector clock for tracking causality in distributed systems.
    Based on community-learned consensus patterns.
    """
    
    def __init__(self, node_id: str, clock: Optional[Dict[str, int]] = None):
        self.node_id = node_id
        self.clock = clock or {node_id: 0}
    
    def increment(self) -> 'VectorClock':
        """Increment this node's counter."""
        self.clock[self.node_id] = self.clock.get(self.node_id, 0) + 1
        return self
    
    def merge(self, other: 'VectorClock') -> 'VectorClock':
        """Merge two vector clocks (taking element-wise max)."""
        result = deepcopy(self)
        for node, count in other.clock.items():
            result.clock[node] = max(result.clock.get(node, 0), count)
        return result
    
    def compare(self, other: 'VectorClock') -> Optional[str]:
        """
        Compare two vector clocks.
        Returns: 'before', 'after', 'concurrent', or 'equal'
        """
        if self.clock == other.clock:
            return 'equal'
        
        # Check if self < other (all entries <= and at least one <)
        all_less_or_equal = all(
            self.clock.get(k, 0) <= other.clock.get(k, 0)
            for k in set(self.clock) | set(other.clock)
        )
        all_greater_or_equal = all(
            self.clock.get(k, 0) >= other.clock.get(k, 0)
            for k in set(self.clock) | set(other.clock)
        )
        
        strictly_less = any(
            self.clock.get(k, 0) < other.clock.get(k, 0)
            for k in other.clock
        )
        strictly_greater = any(
            self.clock.get(k, 0) > other.clock.get(k, 0)
            for k in self.clock
        )
        
        if all_less_or_equal and strictly_less:
            return 'before'  # self happened before other
        if all_greater_or_equal and strictly_greater:
            return 'after'  # self happened after other
        
        return 'concurrent'  # no causal relationship
    
    def to_dict(self) -> Dict[str, int]:
        """Serialize to dict."""
        return deepcopy(self.clock)
    
    @classmethod
    def from_dict(cls, node_id: str, data: Dict[str, int]) -> 'VectorClock':
        """Deserialize from dict."""
        return cls(node_id, deepcopy(data))
    
    def __repr__(self) -> str:
        return f"VectorClock({self.node_id}: {self.clock})"


class VectorClockMerger:
    """Utility for merging vector clocks in gossip protocols."""
    
    @staticmethod
    def resolve_conflict(clock1: VectorClock, clock2: VectorClock, tiebreaker: str = 'timestamp') -> VectorClock:
        """
        Resolve concurrent updates using tiebreaker.
        For now: use lexicographical node_id ordering as deterministic tiebreaker.
        """
        result = clock1.merge(clock2)
        # Add tiebreaker metadata
        result.clock[f"_resolved_by_{tiebreaker}"] = 1
        return result
