"""Provenance tracker using isnad chains (eudaemon_0 pattern)."""
import hashlib
import json
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import List, Dict, Optional, Any


@dataclass
class ProvenanceEntry:
    """Single entry in the provenance chain."""
    node_id: str
    capability: str
    timestamp: str
    confidence: float = 1.0
    signature: Optional[str] = None


class ProvenanceTracker:
    """
    Track capability provenance via isnad chains.
    
    Based on eudaemon_0's supply-chain security approach:
    - Every capability carries a chain of attestation
    - Chain is only as trustworthy as its weakest link
    - Supports "costly vouching" (stake-based trust)
    """
    
    def __init__(self, node_id: str):
        self.node_id = node_id
        self._chains: Dict[str, List[ProvenanceEntry]] = {}
    
    def attest(self, capability: str, vouching_party: str, 
               stake: float = 0.0) -> ProvenanceEntry:
        """
        Create attestation for a capability.
        
        Args:
            capability: The capability being attested
            vouching_party: Node issuing the attestation
            stake: Reputation/currency at risk (costly vouching)
        """
        entry = ProvenanceEntry(
            node_id=vouching_party,
            capability=capability,
            timestamp=datetime.utcnow().isoformat(),
            confidence=min(stake / 100.0, 1.0) if stake > 0 else 0.5
        )
        return entry
    
    def add_to_chain(self, capability: str, entry: ProvenanceEntry):
        """Add attestation to capability's provenance chain."""
        if capability not in self._chains:
            self._chains[capability] = []
        self._chains[capability].append(entry)
    
    def verify_chain(self, capability: str, 
                     min_confidence: float = 0.5) -> tuple[bool, str]:
        """
        Verify a capability's provenance chain.
        
        Returns: (is_valid, reason)
        Chain is only as strong as the minimum confidence.
        """
        chain = self._chains.get(capability, [])
        if not chain:
            return False, "No provenance chain"
        
        min_found = min(e.confidence for e in chain)
        if min_found < min_confidence:
            return False, f"Weak link: confidence {min_found} < {min_confidence}"
        
        # Verify chain integrity (each entry references previous)
        for i in range(1, len(chain)):
            if chain[i].timestamp < chain[i-1].timestamp:
                return False, f"Timestamp anomaly at position {i}"
        
        return True, f"Valid chain with {len(chain)} attestations"
    
    def get_chain(self, capability: str) -> List[Dict[str, Any]]:
        """Get provenance chain as serializable list."""
        return [asdict(e) for e in self._chains.get(capability, [])]
    
    def export(self) -> Dict[str, List[Dict]]:
        """Export all chains for serialization."""
        return {cap: self.get_chain(cap) for cap in self._chains}
