import os
import requests
import json
import random
from typing import List, Dict, Any
from core.redis import redis
import time
from fastapi.concurrency import run_in_threadpool

RPM_LIMIT = 5
RPD_LIMIT = 20
BASE_429_BACKOFF_SECONDS = 30
MAX_429_BACKOFF_SECONDS = 600
BACKOFF_JITTER_SECONDS = 5
SHORT_503_COOLDOWN_SECONDS = 30


class GeminiService:
    def __init__(self):
        # Load all keys from a single comma-separated env var
        raw = os.getenv("GEMINI_API_KEYS", "")
        self.api_keys = [k.strip() for k in raw.replace("\n", ",").split(",") if k.strip()]

        # Legacy support for GEMINI_API_KEY if GEMINI_API_KEYS is not set
        legacy_key = os.getenv("GEMINI_API_KEY")
        if legacy_key and not self.api_keys:
            self.api_keys = [legacy_key]
            print(" [GEMINI SERVICE] Using legacy GEMINI_API_KEY")

        if not self.api_keys:
            raise ValueError(
                "At least one Gemini API key is required. "
                "Set GEMINI_API_KEYS=key1,key2,... (or legacy GEMINI_API_KEY) in your .env file."
            )

        self.model = "gemini-2.5-flash"
        self.base_url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"

        print(f" [GEMINI SERVICE] Initialized with {len(self.api_keys)} API key(s)")
    
    async def seed_gemini_keys(self, redis):
        keys = self.api_keys

        for idx, api_key in enumerate(keys, start=1):
            key_id = f"key{idx}"
            redis_key = f"gemini:key:{key_id}"

            exists = await redis.exists(redis_key)

            if exists:
                # Clear stale runtime state, preserve daily count
                await redis.hset(redis_key, mapping={
                    "cooldown_until": 0,
                    "rpm_count": 0,
                    "rpm_window": 0,
                })
            else:
                await redis.hset(redis_key, mapping={
                    "api_key": api_key,
                    "cooldown_until": 0,
                    "rpm_count": 0,
                    "rpm_window": 0,
                    "rpd_count": 0,
                    "rpd_window": 0,
                    "consecutive_429": 0,
                    "backoff_seconds": 0,
                    "last_used_at": 0,
                    "last_429_at": 0,
                })
                await redis.sadd("gemini:keys", key_id)

        print(f"✅ Seeded {len(keys)} Gemini keys into Redis")
           
        
    async def _get_available_api_key(self) -> tuple[str, str]:
        now = int(time.time())
        key_ids = list(await redis.smembers("gemini:keys"))
        random.shuffle(key_ids)
        candidates = []

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
                continue

            candidates.append((key_id, data))

        candidates.sort(
            key=lambda item: (
                int(item[1].get("consecutive_429", 0)),
                int(item[1].get("last_used_at", 0)),
            )
        )

        for key_id, data in candidates:
            redis_key = f"gemini:key:{key_id}"

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

            await redis.hset(redis_key, mapping={"last_used_at": now})
            return key_id, data["api_key"]

        raise RuntimeError("All Gemini API keys are at capacity or exhausted for today")

    def _get_retry_after_seconds(self, response) -> int | None:
        if response is None:
            return None
        try:
            retry_after = response.headers.get("Retry-After")
            if not retry_after:
                return None
            return max(1, int(float(retry_after)))
        except Exception:
            return None

    async def _rollback_claimed_counts(self, redis_key: str):
        rpm = await redis.hincrby(redis_key, "rpm_count", -1)
        rpd = await redis.hincrby(redis_key, "rpd_count", -1)
        if rpm < 0:
            await redis.hset(redis_key, "rpm_count", 0)
        if rpd < 0:
            await redis.hset(redis_key, "rpd_count", 0)

    async def _handle_429(self, key_id: str, response=None):
        now = int(time.time())
        is_daily_exhausted = False
        redis_key = f"gemini:key:{key_id}"

        if response is not None:
            try:
                error_message = response.json().get("error", {}).get("message", "").lower()
                daily_indicators = ["daily", "quota", "billing", "monthly"]
                is_daily_exhausted = any(i in error_message for i in daily_indicators)
            except Exception:
                pass

        await self._rollback_claimed_counts(redis_key)

        if is_daily_exhausted:
            await redis.hset(
                redis_key,
                mapping={
                    "rpd_count": RPD_LIMIT,
                    "cooldown_until": now + 86400,
                    "last_429_at": now,
                },
            )
        else:
            data = await redis.hgetall(redis_key)
            retry_after = self._get_retry_after_seconds(response)
            if retry_after is None:
                prev = int(data.get("backoff_seconds", 0))
                retry_after = prev * 2 if prev > 0 else BASE_429_BACKOFF_SECONDS
            retry_after = min(retry_after, MAX_429_BACKOFF_SECONDS)
            retry_after += random.randint(0, BACKOFF_JITTER_SECONDS)
            consecutive = int(data.get("consecutive_429", 0)) + 1
            await redis.hset(
                redis_key,
                mapping={
                    "cooldown_until": now + retry_after,
                    "backoff_seconds": retry_after,
                    "consecutive_429": consecutive,
                    "last_429_at": now,
                },
            )

    async def _handle_503(self, key_id: str):
        now = int(time.time())
        redis_key = f"gemini:key:{key_id}"
        await self._rollback_claimed_counts(redis_key)
        cooldown = SHORT_503_COOLDOWN_SECONDS + random.randint(0, BACKOFF_JITTER_SECONDS)
        await redis.hset(redis_key, "cooldown_until", now + cooldown)

    async def mark_key_success(self, key_id: str):
        now = int(time.time())
        await redis.hset(
            f"gemini:key:{key_id}",
            mapping={
                "consecutive_429": 0,
                "backoff_seconds": 0,
                "last_used_at": now,
            },
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
 
        
    async def _make_api_request(self, data, max_retries=3, user: str = None):
        last_error = None

        for attempt in range(max_retries):
            key_id, api_key = await self._get_available_api_key()

            headers = {
                "Content-Type": "application/json",
                "X-goog-api-key": api_key,
            }

            try:
                print(f"🌐 Using {key_id} (attempt {attempt + 1})")

                response = await run_in_threadpool(
                    requests.post,
                    self.base_url,
                    headers=headers,
                    json=data,
                )

                if response.status_code == 200:
                    await self.mark_key_success(key_id)
                    return response, None, key_id

                if self._is_rate_limit_error(response):
                    print(f"⚠️ Rate limit hit on {key_id}")
                    await self._handle_429(key_id, response)
                    last_error = "Rate limited"
                    continue

                if response.status_code == 503:
                    print(f"⚠️ Service unavailable on {key_id}")
                    await self._handle_503(key_id)
                    last_error = "Service unavailable"
                    continue

                return None, f"API error {response.status_code}: {response.text}", key_id

            except requests.RequestException as e:
                last_error = str(e)

        return None, f"Retries exhausted: {last_error}", None

    async def chat(self,messages: List[Dict[str, str]],max_tokens: int = 3000,user: str = None) -> Dict[str, Any]:
        try:
            contents = []
            print("USER VALUE:", user, type(user))
            for msg in messages:
                if msg.get("role") == "user":
                    contents.append({"parts": [{"text": msg["content"]}]})
                elif msg.get("role") == "assistant":
                    contents.append({"parts": [{"text": f"Assistant: {msg['content']}"}]})

            if messages and messages[0].get("role") == "system" and contents:
                contents[0]["parts"][0]["text"] = (
                    messages[0]["content"] + "\n\n" + contents[0]["parts"][0]["text"]
                )

            data = {"contents": contents}

            response, error, key_id = await self._make_api_request(data, user=user)

            if error:
                return {"success": False, "error": error}

            result = response.json()
            content = (
                result["candidates"][0]["content"]["parts"][0]["text"]
                if result.get("candidates")
                else "No response generated"
            )

            return {
                "success": True,
                "response": content,
                "api_key_used": key_id,
                "usage": result.get("usage", {}),
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def generate_sprint_plan(self, conversation_history: List[Dict[str, str]], prompt_data: str = None) -> Dict[str, Any]:
        """Generate a comprehensive sprint plan based on conversation history"""
        try:
            # Use the provided prompt data from global variable
            print(f"🔍 [GEMINI SERVICE] Received prompt_data type: {type(prompt_data)}")
            print(f"🔍 [GEMINI SERVICE] Received prompt_data length: {len(prompt_data) if prompt_data else 0} characters")
            print(f"🔍 [GEMINI SERVICE] Received prompt_data preview: {prompt_data[:100] if prompt_data else 'None'}...")
            
            if not prompt_data:
                print("❌ [GEMINI SERVICE] No prompt data provided")
                return {
                    "success": False,
                    "response": "No prompt data provided. Please ensure prompt is loaded from database.",
                    "error": "Missing prompt data"
                }
            
            system_prompt = prompt_data
            print(f"📦 [GEMINI SERVICE] Using system_prompt: {system_prompt[:100]}...")
            
            # Combine system prompt with conversation history
            messages = [{"role": "system", "content": system_prompt}]
            messages.extend(conversation_history)
            
            # Add final instruction
            messages.append({
                "role": "user", 
                "content": "Based on our conversation, please create a comprehensive sprint plan with all the details we discussed."
            })
            
            return self.chat(messages, max_tokens=3000)
            
        except Exception as e:
            return {
                "success": False,
                "response": f"Error generating sprint plan: {str(e)}",
                "error": str(e)
            }

    def generate_risk_assessment(self, conversation_history: List[Dict[str, str]], prompt_data: str = None) -> Dict[str, Any]:
        """Generate a comprehensive risk assessment based on conversation history"""
        try:
            # Use the provided prompt data from global variable
            print(f"🔍 [GEMINI SERVICE] Received prompt_data type: {type(prompt_data)}")
            print(f"🔍 [GEMINI SERVICE] Received prompt_data length: {len(prompt_data) if prompt_data else 0} characters")
            print(f"🔍 [GEMINI SERVICE] Received prompt_data preview: {prompt_data[:100] if prompt_data else 'None'}...")
            
            if not prompt_data:
                print("❌ [GEMINI SERVICE] No prompt data provided")
                return {
                    "success": False,
                    "response": "No prompt data provided. Please ensure prompt is loaded from database.",
                    "error": "Missing prompt data"
                }
            
            system_prompt = prompt_data
            print(f"📦 [GEMINI SERVICE] Using system_prompt: {system_prompt[:100]}...")
            
            # Combine system prompt with conversation history
            messages = [{"role": "system", "content": system_prompt}]
            messages.extend(conversation_history)
            
            # Add final instruction
            messages.append({
                "role": "user", 
                "content": "Based on our conversation, please create a comprehensive risk assessment with all the details we discussed."
            })
            
            return self.chat(messages, max_tokens=3000)
            
        except Exception as e:
            return {
                "success": False,
                "response": f"Error generating risk assessment: {str(e)}",
                "error": str(e)
            }

    def validate_and_finetune_sprint_plan(self, original_plan: str, user_inputs: str, stored_prompt: str, expected_pb_count: int) -> Dict[str, Any]:
        """Validate and fine-tune the generated sprint plan to ensure ALL PBs are included"""
        try:
            print(f"🔍 [VALIDATION] Starting sprint plan validation for {expected_pb_count} expected PBs...")
            
            # Create validation prompt
            validation_prompt = f"""
You are a quality assurance expert for sprint planning. Your task is to validate and improve the generated sprint plan.

ORIGINAL USER INPUTS:
{user_inputs}

GENERATED SPRINT PLAN TO VALIDATE:
{original_plan}

CRITICAL VALIDATION REQUIREMENTS:
1. **PB Count Verification**: The user provided {expected_pb_count} Product Backlog Items (PBs) in their input
2. **Committed Sprint Backlog**: ALL {expected_pb_count} PBs must be present in this section
3. **Detailed Task Breakdown**: ALL {expected_pb_count} PBs must have detailed task breakdowns
4. **Section Completeness**: The plan MUST include ALL required sections:
   - Sprint Overview
   - Confirmed Sprint Goal  
   - Team Capacity & Availability
   - Committed Sprint Backlog
   - Detailed Task Breakdown (CRITICAL - This section is MISSING!)
   - Definition of Done (DoD)
   - Capacity vs. Committed Effort Summary
   - Risk Management Plan
   - Key Collaboration Points & Handoffs
   - Sprint Confidence
   - Sprint Confidence Improvement Recommendations
VALIDATION INSTRUCTIONS:
- First, check if "Detailed Task Breakdown" section exists in the plan
- If "Detailed Task Breakdown" section is MISSING, the plan is INCOMPLETE
- Count the PBs in the "Committed Sprint Backlog" section
- Count the PBs in the "Detailed Task Breakdown" section (if it exists)
- If either section has fewer than {expected_pb_count} PBs, the plan is INCOMPLETE
- If the plan is incomplete, regenerate the ENTIRE sprint plan with ALL {expected_pb_count} PBs included
- Ensure each PB has comprehensive task breakdown with specific, actionable tasks
- Maintain the same professional HTML format and structure

RESPONSE FORMAT:
- If validation passes: Return the original plan with "✅ VALIDATION PASSED - All {expected_pb_count} PBs included"
- If validation fails: Return the improved plan with "🔄 PLAN REGENERATED - All {expected_pb_count} PBs now included"
- Always maintain the same HTML structure and format as the original plan

Please validate this sprint plan and ensure ALL {expected_pb_count} Product Backlog Items are included in both sections, especially the Detailed Task Breakdown section.
"""

            # Create validation messages
            validation_messages = [
                {"role": "system", "content": stored_prompt},
                {"role": "user", "content": validation_prompt}
            ]
            
            print("🔍 [VALIDATION] Sending validation request to Gemini...")
            
            # Call Gemini for validation
            validation_result = self.chat(validation_messages, max_tokens=4000)
            
            if validation_result["success"]:
                validated_plan = validation_result["response"]
                print("✅ [VALIDATION] Validation completed successfully")
                
                # Check if plan was improved or passed validation
                if "🔄 PLAN REGENERATED" in validated_plan:
                    print(f"🔄 [VALIDATION] Plan was regenerated to include all {expected_pb_count} PBs")
                    # Remove the regeneration marker for clean response
                    validated_plan = validated_plan.replace("🔄 PLAN REGENERATED - All {expected_pb_count} PBs now included", "").strip()
                elif "✅ VALIDATION PASSED" in validated_plan:
                    print(f"✅ [VALIDATION] Plan passed validation with all {expected_pb_count} PBs")
                    # Remove the validation marker for clean response
                    validated_plan = validated_plan.replace("✅ VALIDATION PASSED - All {expected_pb_count} PBs included", "").strip()
                
                return {
                    "success": True,
                    "response": validated_plan,
                    "validated": True,
                    "improved": "🔄 PLAN REGENERATED" in validation_result["response"],
                    "expected_pb_count": expected_pb_count
                }
            else:
                print(f"❌ [VALIDATION] Validation failed: {validation_result.get('error', 'Unknown error')}")
                # Return original plan if validation fails
                return {
                    "success": True,
                    "response": original_plan,
                    "validated": False,
                    "improved": False,
                    "validation_error": validation_result.get("error", "Validation failed"),
                    "expected_pb_count": expected_pb_count
                }
                
        except Exception as e:
            print(f"❌ [VALIDATION] Validation error: {str(e)}")
            # Return original plan if validation process fails
            return {
                "success": True,
                "response": original_plan,
                "validated": False,
                "improved": False,
                "validation_error": str(e),
                "expected_pb_count": expected_pb_count
            }

    def validate_and_finetune_risk_assessment(self, original_assessment: str, user_inputs: str, stored_prompt: str, expected_risk_count: int) -> Dict[str, Any]:
        """Validate and fine-tune the generated risk assessment to ensure ALL risks are included and format is correct"""
        try:
            print(f"🔍 [RISK VALIDATION] Starting risk assessment validation for {expected_risk_count} expected risks...")
            
            # Create validation prompt
            validation_prompt = f"""
You are a quality assurance expert for risk assessment. Your task is to validate and improve the generated risk assessment.

ORIGINAL USER INPUTS:
{user_inputs}

GENERATED RISK ASSESSMENT TO VALIDATE:
{original_assessment}

CRITICAL VALIDATION REQUIREMENTS:
1. **Risk Count Verification**: The user provided {expected_risk_count} risks in their input
2. **Risk Register**: Generate a Risk Register with ALL {expected_risk_count} risks
3. **Risk Confidence Section**: After the Risk Register, include a Risk Confidence section
4. **Output Format Compliance**: Each risk MUST follow the exact HTML format:
   <div class="risk-section">
   <h3>Risk ID: [Issue Key]</h3>
   <p><strong>Risk Description:</strong> [Synthesized Description]</p>
   <p><strong>Severity:</strong> [Mapped Priority/Inferred Severity]</p>
   <p><strong>Status:</strong> [Current Status]</p>
   <p><strong>Risk Owner:</strong> [Assignee/Reporter/Creator]</p>
   <p><strong>Date Identified:</strong> [Created Date]</p>
   <p><strong>Mitigation Plan:</strong> [Extracted/Synthesized Mitigation, or N/A]</p>
   <p><strong>Relevant Notes:</strong> [Summarized Comments/Context, or N/A]</p>
   </div>

VALIDATION INSTRUCTIONS:
- Count the risks in the output
- Verify each risk follows the exact HTML format specified above
- Ensure ALL {expected_risk_count} risks are included
- Do NOT include any other sections (Executive Summary, Project Overview, Risk Categories Analysis, Stakeholder Assessment, Risk Matrix, etc.)
- If any risks are missing, regenerate the ENTIRE Risk Register with ALL {expected_risk_count} risks included
- Use proper HTML formatting with <div class="risk-section"> for each risk
- Do NOT use asterisks (*) or markdown formatting
- Focus only on the 8 specified fields for each risk
- Do NOT include any validation messages or status indicators

RISK CONFIDENCE SECTION REQUIREMENTS:
After the Risk Register, include a "Risk Confidence" section with the following format:
   <div class="risk-confidence-section">
   <h2>Risk Confidence</h2>
   <p><strong>Confidence Score:</strong> [Score out of 10 or percentage] for achieving the Sprint Goal</p>
   <p><strong>Rationale:</strong> [Brief explanation of the confidence score, considering the plan, identified risks, severity of risks, mitigation strategies, and team capacity]</p>
   </div>

The confidence score should:
- Be based on the analysis of all identified risks
- Consider risk severity and mitigation plans
- Take into account team capacity and project scope
- Provide actionable insights for stakeholders

RESPONSE FORMAT:
- Return the Risk Register followed by the Risk Confidence section
- Use proper HTML formatting with appropriate div classes
- Do NOT include any validation messages like "✅ VALIDATION PASSED" or "🔄 ASSESSMENT REGENERATED"
- Always maintain clean HTML structure with proper sections

Please validate this risk assessment and ensure ALL {expected_risk_count} risks are included with the correct format, removing any unnecessary stakeholder information.
"""
            
            print(f"🔍 [RISK VALIDATION] Validation prompt length: {len(validation_prompt)}")
            
            # Call Gemini with validation prompt
            messages = [
                {"role": "system", "content": validation_prompt},
                {"role": "user", "content": f"Please validate and improve this risk assessment to ensure all {expected_risk_count} risks are included with proper formatting. Also include a Risk Confidence section at the end with a confidence score and rationale."}
            ]
            
            print("🔍 [RISK VALIDATION] Calling Gemini service for validation...")
            gemini_response = self.chat(messages, max_tokens=4000)
            
            if not gemini_response or not gemini_response.get('success', False):
                error_msg = gemini_response.get('response', 'Unknown error from Gemini service') if gemini_response else 'No response from Gemini'
                print(f"❌ [RISK VALIDATION] Gemini service failed: {error_msg}")
                return {
                    "success": False,
                    "response": f"Validation failed: {error_msg}",
                    "error": error_msg
                }
            
            validation_result = gemini_response.get('response', '')
            print(f"✅ [RISK VALIDATION] Validation completed successfully!")
            print(f"📊 [RISK VALIDATION] Result length: {len(validation_result)} characters")
            print(f"📊 [RISK VALIDATION] Result preview: {validation_result[:200]}...")
            
            return {
                "success": True,
                "response": validation_result,
                "message": "Risk assessment validation completed successfully"
            }
            
        except Exception as e:
            print(f"❌ [RISK VALIDATION] Error: {str(e)}")
            return {
                "success": False,
                "response": f"Validation failed: {str(e)}",
                "error": str(e)
            }

gemini_service = GeminiService()
