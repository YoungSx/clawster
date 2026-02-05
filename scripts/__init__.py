"""
OpenClaw Distributed Skill - Module Initialization

This module provides distributed functionality for OpenClaw nodes including:
- Node lifecycle management
- Leader election with Redis RedLock
- Memory/state synchronization

Usage:
    from openclaw_distributed import NodeManager, LeaderElection, StateSync
"""

__version__ = "0.1.0"
__author__ = "OpenClaw"

from .node_manager import NodeManager
from .leader_election import LeaderElection
from .state_sync import StateSync

__all__ = [
    "NodeManager",
    "LeaderElection",
    "StateSync",
]


def create_cluster_node(node_id: str, redis_host: str = "localhost", redis_port: int = 6379,
                        redis_password: str = None, redis_db: int = 0) -> "ClusterNode":
    """
    Factory function to create a fully configured cluster node.
    
    Args:
        node_id: Unique identifier for this node
        redis_host: Redis server hostname
        redis_port: Redis server port
        redis_password: Redis password (optional)
        redis_db: Redis database number
    
    Returns:
        ClusterNode: A configured cluster node instance
    """
    return ClusterNode(node_id, redis_host, redis_port, redis_password, redis_db)


class ClusterNode:
    """
    High-level interface for OpenClaw cluster participation.
    Combines all distributed components into a single interface.
    """
    
    def __init__(self, node_id: str, redis_host: str, redis_port: int,
                 redis_password: str = None, redis_db: int = 0):
        self.node_id = node_id
        self.node_manager = NodeManager(node_id, redis_host, redis_port, redis_password, redis_db)
        self.leader_election = LeaderElection(node_id, redis_host, redis_port, redis_password, redis_db)
        self.state_sync = StateSync(node_id, redis_host, redis_port, redis_password, redis_db)
    
    def start(self):
        """Start all cluster services."""
        self.node_manager.register_node()
        self.leader_election.start()
        self.state_sync.start()
    
    def stop(self):
        """Gracefully stop all cluster services."""
        self.state_sync.stop()
        self.leader_election.stop()
        self.node_manager.shutdown()
    
    @property
    def is_leader(self) -> bool:
        """Check if this node is the current leader."""
        return self.leader_election.is_leader
    
    def publish_memory(self, key: str, value: dict):
        """Publish a memory update to the cluster."""
        self.state_sync.publish_event("memory_update", key, value)
