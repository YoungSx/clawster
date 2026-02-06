import redis
import threading
from typing import Dict, Any, Optional

_redis_connection_pool: Optional[redis.ConnectionPool] = None
_redis_pool_lock = threading.Lock()

def get_redis_client(**kwargs) -> redis.Redis:
    """
    Retrieves a redis-py client instance with connection pooling.
    This function ensures a single connection pool is created and reused
    across the application for optimal performance and resource management.

    Args:
        host (str): Redis host. Defaults to 'localhost'.
        port (int): Redis port. Defaults to 6379.
        db (int): Redis database number. Defaults to 0.
        password (str, optional): Redis password.
        max_connections (int): Maximum number of connections in the pool. Defaults to 10.
        decode_responses (bool): Decode Redis responses to Python strings. Defaults to True.
        # Add other redis.ConnectionPool arguments as needed

    Returns:
        redis.Redis: A redis-py client instance.
    """
    global _redis_connection_pool

    # Extract connection pool specific arguments from kwargs
    pool_kwargs = {
        'host': kwargs.pop('host', 'localhost'),
        'port': kwargs.pop('port', 6379),
        'db': kwargs.pop('db', 0),
        'password': kwargs.pop('password', None),
        'max_connections': kwargs.pop('max_connections', 10),
        # Add other relevant ConnectionPool args here if needed
    }

    # Redis client specific arguments
    client_kwargs = {
        'decode_responses': kwargs.pop('decode_responses', True),
        **kwargs # Pass any remaining kwargs to the Redis client
    }

    if _redis_connection_pool is None:
        with _redis_pool_lock:
            if _redis_connection_pool is None:
                print(f"Creating new Redis ConnectionPool with config: {pool_kwargs}")
                _redis_connection_pool = redis.ConnectionPool(**pool_kwargs)

    # Always create a new Redis client instance from the pool for thread safety
    # The client itself is not thread-safe, but the pool is.
    return redis.Redis(connection_pool=_redis_connection_pool, **client_kwargs)

if __name__ == '__main__':
    # Example usage and testing
    print("Testing common_redis.py module...")

    # Configure Redis connection (replace with actual config if needed)
    redis_config = {
        'host': 'localhost',
        'port': 6379,
        'db': 0,
        'password': None, # Replace with your Redis password if any
        'max_connections': 5
    }

    try:
        # Get client 1
        client1 = get_redis_client(**redis_config)
        client1.set('test_key_common_redis', 'test_value_1')
        print(f"Client 1 set 'test_key_common_redis': {client1.get('test_key_common_redis')}")

        # Get client 2 (should reuse the same pool)
        client2 = get_redis_client(**redis_config)
        print(f"Client 2 got 'test_key_common_redis': {client2.get('test_key_common_redis')}")

        # Verify both clients use the same connection pool
        assert client1.connection_pool is client2.connection_pool
        print("Both clients use the same connection pool. (Assertion Passed)")

        client1.delete('test_key_common_redis')
        print("Test key deleted.")
        print("common_redis.py testing complete.")

    except redis.exceptions.ConnectionError as e:
        print(f"Could not connect to Redis: {e}")
        print("Please ensure a Redis server is running at localhost:6379 or update redis_config.")
    except Exception as e:
        print(f"An unexpected error occurred during testing: {e}")