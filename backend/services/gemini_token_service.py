import os
import requests
import json
from typing import List, Dict, Any
from core.redis import redis
import time

class GeminiTokenService:
    def __init__(self):
        # Initialize API keys with fallback support
        self.api_keys = [
            os.getenv("GEMINI_API_KEY_1"),      # Primary API key
            os.getenv("GEMINI_API_KEY_2"),      # Secondary API key  
            os.getenv("GEMINI_API_KEY_3"),      # Tertiary API key
            os.getenv("GEMINI_API_KEY_4"),
            os.getenv("GEMINI_API_KEY_5"),
            os.getenv("GEMINI_API_KEY_6"),
            os.getenv("GEMINI_API_KEY_7"),
            os.getenv("GEMINI_API_KEY_8"),
            os.getenv("GEMINI_API_KEY_9"),
            os.getenv("GEMINI_API_KEY_10"),
        ]
        
        # Add legacy support for GEMINI_API_KEY if no numbered keys are set
        legacy_key = os.getenv("GEMINI_API_KEY")
        if legacy_key and not any(self.api_keys):
            self.api_keys = [legacy_key]
            print("🔑 [GEMINI SERVICE] Using legacy GEMINI_API_KEY")
        
        # Filter out None values and ensure we have at least one key
        self.api_keys = [key for key in self.api_keys if key]
        
        if not self.api_keys:
            raise ValueError("At least one GEMINI_API_KEY environment variable is required. Please set GEMINI_API_KEY_1, GEMINI_API_KEY_2, or GEMINI_API_KEY_3 in your .env file.")
        
        
        print(f"🔑 [GEMINI SERVICE] Initialized with {len(self.api_keys)} API key(s)")
    
    async def seed_gemini_keys(self,redis):
        keys = [
            os.getenv("GEMINI_API_KEY_1"),
            os.getenv("GEMINI_API_KEY_2"),
            os.getenv("GEMINI_API_KEY_3"),
        ]

        keys = [k for k in keys if k]

        for idx, api_key in enumerate(keys, start=1):
            key_id = f"key{idx}"
            redis_key = f"gemini:key:{key_id}"

            exists = await redis.exists(redis_key)
            if exists:
                continue

            await redis.hset(
                redis_key,
                mapping={
                    "api_key": api_key,
                    "in_use": 0,
                    "cooldown_until": 0,
                    "successful_hits": 0,
                    "last_used": 0,
                    "user":""

                }
            )

            await redis.sadd("gemini:keys", key_id)

        print(f"✅ Seeded {len(keys)} Gemini c keys into Redis")
        print(f"🔑 [GEMINI SERVICE] seeded from root")
           
        
    async def _get_available_api_key(self, user: str = None) -> tuple[str, str]:
        now = int(time.time())
        candidates = []

        # First: check if user already has a key assigned
        for raw_id in await redis.smembers("gemini:keys"):
            key_id = raw_id
            redis_key = f"gemini:key:{key_id}"
            data = await redis.hgetall(redis_key)

            if not data:
                continue

            # If this key belongs to this user
            if data.get("user") == user:
                hits = int(data.get("successful_hits", 0))

                # If user hasn't exhausted 5 hits → reuse this key
                if hits <= 5:
                    await redis.hset(redis_key, "in_use", 1)
                    return key_id, data["api_key"]

                # If exhausted → unassign user
                await redis.hset(redis_key, mapping={
                    "user": "",
                    "successful_hits": 0,
                    "cooldown_until": int(time.time()) + 60,

                })

        # Second: find a free key
        for raw_id in await redis.smembers("gemini:keys"):
            key_id = raw_id  # Already a string since decode_responses=True
            redis_key = f"gemini:key:{key_id}"

            data = await redis.hgetall(redis_key)
            if not data:
                continue
            if int(data.get("in_use", 0)) == 1:
                continue
            if int(data.get("cooldown_until", 0)) > now:
                continue
            
            hits = int(data.get("successful_hits", 0))
            last_used = int(data.get("last_used", 0))
            candidates.append((hits, last_used, key_id, data["api_key"]))

        if not candidates:
            raise RuntimeError("No available Gemini API keys")
            # least hits, then least recently used
        candidates.sort(key=lambda x: (x[0], x[1]))
        print(f"Candidates: {candidates}")

        _, _, key_id, api_key = candidates[0]

        await redis.hset(
            f"gemini:key:{key_id}",
            mapping={
                "in_use": 1,
                "last_used": now,
            },
        )
        return key_id, api_key  # Already a string since decode_responses=True


    async def _release_key(self, key_id: str):
        await redis.hset(f"gemini:key:{key_id}", "in_use", 0)
        
    async def _set_success_hit(self, key_id: str, user: str):
        await redis.hincrby(f"gemini:key:{key_id}", "successful_hits", 1)
        await redis.hset(
        f"gemini:key:{key_id}",
        mapping={
        "last_used": int(time.time()),
        "user" : user
        }                   
        )    

    def _is_rate_limit_error(self, response):
        """Check if the response indicates a rate limit error"""
        if response.status_code == 429:  # Too Many Requests
            return True
        
        try:
            error_data = response.json()
            error_message = error_data.get('error', {}).get('message', '').lower()
            # Check for common rate limit indicators
            rate_limit_indicators = [
                'quota exceeded',
                'rate limit',
                'too many requests',
                'quota has been exceeded',
                'daily limit exceeded',
                'monthly limit exceeded',
                'billing limit exceeded'
            ]
            return any(indicator in error_message for indicator in rate_limit_indicators)
        except:
            return False
 
gemini_token_service = GeminiTokenService()
