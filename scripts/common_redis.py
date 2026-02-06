"""
Redis Client Module for Clawster

Uses redis-py (mature, production-grade) with:
- Connection pooling (built into redis-py)  
- Health checking (redis-py health_check_interval)
- Configuration from environment (standard practice)
- Retry handling (tenacity - robust retry library)
"""
import os
import redis
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type


def get_redis_client() -> redis.Redis:
    """
    Get Redis client using redis-py from_url pattern.
    Configuration via environment variables (12-factor app standard).
    Uses redis-py's built-in connection pool (mature, battle-tested).
    
    Environment:
        REDIS_URL: Full URL redis://:password@host:port/db
        Or: REDIS_HOST, REDIS_PORT, REDIS_PASSWORD, REDIS_DB
    """
    redis_url = os.getenv('REDIS_URL')
    
    if redis_url:
        # from_url handles pool automatically
        return redis.from_url(
            redis_url,
            decode_responses=True,
            health_check_interval=30,
            socket_connect_timeout=5,
            socket_timeout=5
        )
    
    # Individual env vars (fallback)
    return redis.Redis(
        host=os.getenv('REDIS_HOST', 'localhost'),
        port=int(os.getenv('REDIS_PORT', 6379)),
        db=int(os.getenv('REDIS_DB', 0)),
        password=os.getenv('REDIS_PASSWORD'),
        decode_responses=True,
        health_check_interval=30,
        socket_connect_timeout=5,
        socket_timeout=5
    )


@retry(
    retry=retry_if_exception_type((redis.ConnectionError, redis.TimeoutError)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10)
)
def get_redis_client_with_retry() -> redis.Redis:
    """Get Redis client with tenacity retry (mature library, not custom)."""
    client = get_redis_client()
    client.ping()  # Validate immediately
    return client


def test_connection():
    """Simple test - no hardcoded credentials."""
    try:
        client = get_redis_client_with_retry()
        print(f"✅ Redis connected: {client.ping()}")
        return True
    except Exception as e:
        print(f"❌ Redis error: {e}")
        return False


if __name__ == '__main__':
    test_connection()
