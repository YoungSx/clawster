"""Schema validation and definitions for Clawster."""

from .definitions import (
    NODE_OUTPUT_SCHEMA,
    HEARTBEAT_SCHEMA,
    MEMORY_ENTRY_SCHEMA,
)

from .validator import (
    SchemaValidator,
    ValidationError,
    validate_node_output,
    get_validator,
)

from .vector_clock import (
    VectorClock,
    VectorClockMerger,
)

__all__ = [
    'NODE_OUTPUT_SCHEMA',
    'HEARTBEAT_SCHEMA',
    'MEMORY_ENTRY_SCHEMA',
    'SchemaValidator',
    'ValidationError',
    'validate_node_output',
    'get_validator',
    'VectorClock',
    'VectorClockMerger',
]
