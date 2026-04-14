import os
import re
import logging
import random
import requests
import json
from typing import List, Dict, Any
from core.redis import redis
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

RPM_LIMIT = 5
RPD_LIMIT = 20

class GeminiTokenService:
    def __init__(self):
        # Load all keys from a single comma-separated env var
        raw = os.getenv("GEMINI_API_KEYS", "")
        self.api_keys = [k.strip() for k in re.split(r"[,\n]", raw) if k.strip()]

        # Legacy support for GEMINI_API_KEY if GEMINI_API_KEYS is not set
        legacy_key = os.getenv("GEMINI_API_KEY")
        if legacy_key and not self.api_keys:
            self.api_keys = [legacy_key]
            logger.info("[GEMINI SERVICE] Using legacy GEMINI_API_KEY")

        if not self.api_keys:
            raise ValueError(
                "At least one Gemini API key is required. "
                "Set GEMINI_API_KEYS=key1,key2,... (or legacy GEMINI_API_KEY) in your .env file."
            )

        logger.info(f"[GEMINI SERVICE] Initialized with {len(self.api_keys)} API key(s)")

    async def seed_gemini_keys(self, redis):
        keys = self.api_keys

        # Delete all existing gemini keys to clear stale schema fields
        existing_key_ids = await redis.smembers("gemini:keys")
        if existing_key_ids:
            stale_redis_keys = [f"gemini:key:{kid}" for kid in existing_key_ids]
            await redis.delete(*stale_redis_keys)
            await redis.delete("gemini:keys")
            logger.info(f"[GEMINI SERVICE] Cleared {len(existing_key_ids)} existing Gemini keys from Redis")

        # Seed all keys fresh with new schema
        for idx, api_key in enumerate(keys, start=1):
            key_id = f"key{idx}"
            redis_key = f"gemini:key:{key_id}"

            await redis.hset(redis_key, mapping={
                "api_key": api_key,
                "cooldown_until": 0,
                "rpm_count": 0,
                "rpm_window": 0,
                "rpd_count": 0,
                "rpd_window": 0,
            })
            await redis.sadd("gemini:keys", key_id)

        logger.info(f"[GEMINI SERVICE] Seeded {len(keys)} Gemini keys into Redis")

    async def _get_available_api_key(self) -> tuple[str, str]:
        now = int(time.time())

        key_ids = list(await redis.smembers("gemini:keys"))
        random.shuffle(key_ids)  # distribute load evenly across all keys

        for key_id in key_ids:
            redis_key = f"gemini:key:{key_id}"
            data = await redis.hgetall(redis_key)

            if not data:
                continue
            if int(data.get("cooldown_until", 0)) > now:
                continue

            # Roll RPM window if older than 60s
            if now - int(data.get("rpm_window", 0)) >= 60:
                await redis.hset(redis_key, mapping={"rpm_count": 0, "rpm_window": now})

            # Roll RPD window if older than 86400s
            if now - int(data.get("rpd_window", 0)) >= 86400:
                await redis.hset(redis_key, mapping={"rpd_count": 0, "rpd_window": now})

            # Re-fetch after potential resets
            data = await redis.hgetall(redis_key)

            if int(data.get("rpd_count", 0)) >= RPD_LIMIT:
                continue  # key exhausted for the day

            # Atomically claim RPM slot
            new_rpm = await redis.hincrby(redis_key, "rpm_count", 1)
            if new_rpm > RPM_LIMIT:
                await redis.hincrby(redis_key, "rpm_count", -1)
                continue

            # Atomically claim RPD slot
            new_rpd = await redis.hincrby(redis_key, "rpd_count", 1)
            if new_rpd > RPD_LIMIT:
                await redis.hincrby(redis_key, "rpm_count", -1)
                await redis.hincrby(redis_key, "rpd_count", -1)
                continue

            return key_id, data["api_key"]

        raise RuntimeError("All Gemini API keys are at capacity or exhausted for today")

    async def _handle_429(self, key_id: str, response=None):
        is_daily_exhausted = False

        if response is not None:
            try:
                error_message = response.json().get("error", {}).get("message", "").lower()
                daily_indicators = ["daily", "quota", "billing", "monthly"]
                is_daily_exhausted = any(i in error_message for i in daily_indicators)
            except Exception:
                pass

        # Roll back counts — request failed
        await redis.hincrby(f"gemini:key:{key_id}", "rpm_count", -1)
        await redis.hincrby(f"gemini:key:{key_id}", "rpd_count", -1)

        if is_daily_exhausted:
            await redis.hset(f"gemini:key:{key_id}", "rpd_count", RPD_LIMIT)
        else:
            # Cap rpm_count at limit — window will roll over naturally after 60s
            # No cooldown_until so other users aren't blocked longer than necessary
            await redis.hset(f"gemini:key:{key_id}", "rpm_count", RPM_LIMIT)

    async def _handle_503(self, key_id: str):
        now = int(time.time())
        # Roll back counts — request never consumed quota
        await redis.hincrby(f"gemini:key:{key_id}", "rpm_count", -1)
        await redis.hincrby(f"gemini:key:{key_id}", "rpd_count", -1)
        # Short cooldown — Gemini server temporarily unavailable
        await redis.hset(f"gemini:key:{key_id}", "cooldown_until", now + 30)

    def _is_rate_limit_error(self, response):
        if response.status_code == 429:
            return True
        try:
            error_message = response.json().get("error", {}).get("message", "").lower()
            rate_limit_indicators = [
                "quota exceeded",
                "rate limit",
                "too many requests",
                "quota has been exceeded",
                "daily limit exceeded",
                "monthly limit exceeded",
                "billing limit exceeded"
            ]
            return any(indicator in error_message for indicator in rate_limit_indicators)
        except Exception:
            return False

gemini_token_service = GeminiTokenService()
