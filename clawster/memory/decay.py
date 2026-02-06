"""Memory decay filter using ACT-R model (ai-now pattern)."""
import math
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import json


@dataclass
class MemoryEntry:
    """A memory with decay tracking."""
    content: str
    timestamp: datetime
    access_count: int = 0
    last_access: Optional[datetime] = None
    
    def relevance_score(self, current_time: Optional[datetime] = None,
                        half_life_days: float = 30.0) -> float:
        """
        Calculate ACT-R inspired relevance score.
        
        S(t) = S0 * (t^(-d)) where decay_rate = log(2) / half_life
        Boosted by access frequency.
        """
        now = current_time or datetime.utcnow()
        age_days = (now - self.timestamp).total_seconds() / 86400
        
        # Base decay: exponential
        decay_rate = math.log(2) / half_life_days
        base_relevance = math.exp(-decay_rate * age_days)
        
        # Access frequency boost: power law
        if self.access_count > 0:
            boost = math.log(self.access_count + 1) / 5.0
            return min(base_relevance * (1 + boost), 1.0)
        
        return base_relevance


class MemoryDecayFilter:
    """
    Filter memories using ACT-R decay model.
    
    Based on ai-now's approach:
    - 30-day half-life for base memories
    - Access frequency boosts relevance
    - Below threshold = checkpoint/shed
    """
    
    def __init__(self, half_life_days: float = 30.0, 
                 relevance_threshold: float = 0.3):
        self.half_life_days = half_life_days
        self.threshold = relevance_threshold
        self._memories: Dict[str, MemoryEntry] = {}
    
    def add(self, memory_id: str, content: str, 
            timestamp: Optional[datetime] = None):
        """Add memory with initial score."""
        self._memories[memory_id] = MemoryEntry(
            content=content,
            timestamp=timestamp or datetime.utcnow(),
            access_count=0
        )
    
    def access(self, memory_id: str) -> Optional[str]:
        """Access memory and boost its score."""
        if memory_id not in self._memories:
            return None
        
        entry = self._memories[memory_id]
        entry.access_count += 1
        entry.last_access = datetime.utcnow()
        return entry.content
    
    def filter_by_relevance(self, current_time: Optional[datetime] = None) -> Tuple[List[str], List[str]]:
        """
        Filter memories into keep/shed lists.
        
        Returns: (ids_to_keep, ids_to_checkpoint_or_shed)
        """
        now = current_time or datetime.utcnow()
        keep = []
        shed = []
        
        for memory_id, entry in self._memories.items():
            score = entry.relevance_score(now, self.half_life_days)
            if score >= self.threshold:
                keep.append(memory_id)
            else:
                shed.append(memory_id)
        
        return keep, shed
    
    def get_checkpoint_data(self, memory_id: str) -> Optional[Dict]:
        """Get serialized memory for checkpointing."""
        entry = self._memories.get(memory_id)
        if not entry:
            return None
        
        score = entry.relevance_score(half_life_days=self.half_life_days)
        return {
            "content": entry.content,
            "timestamp": entry.timestamp.isoformat(),
            "access_count": entry.access_count,
            "last_access": entry.last_access.isoformat() if entry.last_access else None,
            "relevance_score": score
        }
    
    def post_compression_restore(self, checkpoint_data: List[Dict]):
        """Restore high-value memories after context compression."""
        for data in checkpoint_data:
            memory_id = f"checkpoint_{hash(data['content']) % 10000}"
            self._memories[memory_id] = MemoryEntry(
                content=data["content"],
                timestamp=datetime.fromisoformat(data["timestamp"]),
                access_count=data.get("access_count", 0),
                last_access=datetime.fromisoformat(data["last_access"]) if data.get("last_access") else None
            )
    
    def export_high_value(self) -> List[Dict]:
        """Export memories above threshold for persistence."""
        keep, _ = self.filter_by_relevance()
        return [self.get_checkpoint_data(mid) for mid in keep]
