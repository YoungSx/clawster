"""Schema validation using jsonschema (mature library)."""
from typing import Any, Dict, List, Optional
import jsonschema
from jsonschema import validate, ValidationError as JsonSchemaValidationError

from .definitions import NODE_OUTPUT_SCHEMA, HEARTBEAT_SCHEMA


# Custom exception for validation errors
class ValidationError(Exception):
    """Raised when schema validation fails."""
    pass


class SchemaValidator:
    """Validate messages against JSON schemas using jsonschema library."""
    
    SCHEMAS = {
        'node_output': NODE_OUTPUT_SCHEMA,
        'heartbeat': HEARTBEAT_SCHEMA,
    }
    
    def __init__(self):
        self._cache = {}
    
    def validate(self, data: Dict[str, Any], schema_name: str) -> tuple[bool, Optional[str]]:
        """
        Validate data against a named schema.
        
        Returns: (is_valid, error_message)
        """
        schema = self.SCHEMAS.get(schema_name)
        if not schema:
            return False, f"Unknown schema: {schema_name}"
        
        try:
            validate(instance=data, schema=schema)
            return True, None
        except JsonSchemaValidationError as e:
            return False, f"Validation error: {e.message} at {list(e.path)}"
    
    def validate_node_output(self, data: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Quick validate for node output messages."""
        return self.validate(data, 'node_output')
    
    def validate_heartbeat(self, data: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Quick validate for heartbeat messages."""
        return self.validate(data, 'heartbeat')


# Module-level validator for convenience
_default_validator = None

def get_validator() -> SchemaValidator:
    """Get singleton validator instance."""
    global _default_validator
    if _default_validator is None:
        _default_validator = SchemaValidator()
    return _default_validator


def validate_node_output(data: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    """Module-level convenience function."""
    return get_validator().validate_node_output(data)
