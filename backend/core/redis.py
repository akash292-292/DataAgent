"""
Redis client configuration for PM Portal
Provides async Redis connection for caching, sessions, and rate limiting
"""

import redis.asyncio as redis
import os
from dotenv import load_dotenv

load_dotenv()

# Redis connection configuration
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)

# Create Redis client with connection pooling
redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=REDIS_DB,
    password=REDIS_PASSWORD,
    decode_responses=True,
    socket_connect_timeout=5,
    socket_keepalive=True,
    health_check_interval=30
)

# Export redis client
redis = redis_client

__all__ = ["redis"]