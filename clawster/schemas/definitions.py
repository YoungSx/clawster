"""
JSON Schema Definitions for Clawster

Based on Delamain's TDD approach - strict validation at boundaries.
All node outputs must validate against these schemas before broadcast.
"""

# Schema for node output messages
NODE_OUTPUT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["node_id", "timestamp", "output_type", "payload", "version"],
    "properties": {
        "node_id": {
            "type": "string",
            "pattern": "^[a-zA-Z0-9_-]{3,64}$",
            "description": "Unique identifier for the source node"
        },
        "timestamp": {
            "type": "string",
            "format": "date-time",
            "description": "ISO 8601 timestamp of output generation"
        },
        "output_type": {
            "type": "string",
            "enum": ["inference", "action", "heartbeat", "memory_update", "gossip"],
            "description": "Classification of the output"
        },
        "payload": {
            "type": "object",
            "description": "Type-specific payload data"
        },
        "version": {
            "type": "string",
            "pattern": "^\\d+\\.\\d+\\.\\d+$",
            "description": "Schema version (semver)"
        },
        "provenance": {
            "type": "object",
            "required": ["chain"],
            "properties": {
                "chain": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["node_id", "capability", "timestamp"],
                        "properties": {
                            "node_id": {"type": "string"},
                            "capability": {"type": "string"},
                            "timestamp": {"type": "string", "format": "date-time"},
                            "confidence": {"type": "number", "minimum": 0, "maximum": 1}
                        }
                    },
                    "description": "Isnad chain of capability provenance"
                }
            }
        },
        "vector_clock": {
            "type": "object",
            "additionalProperties": {"type": "integer", "minimum": 0},
            "description": "Lamport-style vector clock for causal ordering"
        },
        "signature": {
            "type": "string",
            "description": "Optional cryptographic signature"
        }
    },
    "additionalProperties": False
}

# Schema for heartbeat messages
HEARTBEAT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["node_id", "timestamp", "capabilities", "vector_clock"],
    "properties": {
        "node_id": {"type": "string"},
        "timestamp": {"type": "string", "format": "date-time"},
        "capabilities": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name", "version"],
                "properties": {
                    "name": {"type": "string"},
                    "version": {"type": "string"},
                    "provenance": {
                        "type": "object",
                        "required": ["source", "verified"],
                        "properties": {
                            "source": {"type": "string"},
                            "verified": {"type": "boolean"},
                            "attestation_chain": {"type": "array", "items": {"type": "string"}}
                        }
                    }
                }
            }
        },
        "vector_clock": {
            "type": "object",
            "additionalProperties": {"type": "integer", "minimum": 0}
        },
        "memory_stats": {
            "type": "object",
            "properties": {
                "total_entries": {"type": "integer", "minimum": 0},
                "active_entries": {"type": "integer", "minimum": 0},
                "decay_factor": {"type": "number", "minimum": 0, "maximum": 1}
            }
        }
    }
}

# Schema for memory entries
MEMORY_ENTRY_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["id", "timestamp", "content", "relevance_score"],
    "properties": {
        "id": {"type": "string"},
        "timestamp": {"type": "string", "format": "date-time"},
        "content": {"type": "object"},
        "relevance_score": {"type": "number", "minimum": 0, "maximum": 1},
        "decay_config": {
            "type": "object",
            "properties": {
                "half_life_days": {"type": "number", "minimum": 0.1},
                "decay_curve": {"type": "string", "enum": ["exponential", "linear", "step"]}
            }
        },
        "tags": {"type": "array", "items": {"type": "string"}},
        "source_node": {"type": "string"}
    }
}

# Schema for gossip protocol messages
GOSSIP_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["message_id", "sender_id", "digest", "vector_clock"],
    "properties": {
        "message_id": {"type": "string"},
        "sender_id": {"type": "string"},
        "digest": {"type": "string"},
        "vector_clock": {"type": "object"},
        "payload_hash": {"type": "string"},
        "ttl": {"type": "integer", "minimum": 0, "maximum": 10}
    }
}
