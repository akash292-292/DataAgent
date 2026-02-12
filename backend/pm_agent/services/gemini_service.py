import os
import requests
import json
from typing import List, Dict, Any

class GeminiService:
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
        
        # Track current API key index and usage
        self.current_key_index = 0
        self.current_api_key = self.api_keys[0]
        self.model = "gemini-2.5-flash"
        self.base_url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"


        
        print(f"🔑 [GEMINI SERVICE] Initialized with {len(self.api_keys)} API key(s)")
        print(f"🔑 [GEMINI SERVICE] Using API key #{self.current_key_index + 1}")
        
    def _switch_to_next_api_key(self):
        """Switch to the next available API key"""
        if self.current_key_index < len(self.api_keys) - 1:
            self.current_key_index += 1
            self.current_api_key = self.api_keys[self.current_key_index]
            print(f"🔄 [GEMINI SERVICE] Switched to API key #{self.current_key_index + 1}")
            return True
        else:
            print(f"❌ [GEMINI SERVICE] All API keys exhausted. No more fallback options.")
            return False
    
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
    
    def _make_api_request(self, headers, data):
        """Make API request with automatic fallback on rate limits"""
        max_retries = len(self.api_keys)
        
        for attempt in range(max_retries):
            try:
                print(f"🌐 [GEMINI SERVICE] Making request with API key #{self.current_key_index + 1} (attempt {attempt + 1})")
                
                response = requests.post(self.base_url, headers=headers, json=data)
                
                # Check if request was successful
                if response.status_code == 200:
                    print(f"✅ [GEMINI SERVICE] Request successful with API key #{self.current_key_index + 1}")
                    return response, None
                
                # Check if it's a rate limit error
                if self._is_rate_limit_error(response):
                    print(f"⚠️ [GEMINI SERVICE] Rate limit hit with API key #{self.current_key_index + 1}")
                    
                    # Try to switch to next API key
                    if self._switch_to_next_api_key():
                        # Update headers with new API key
                        headers["X-goog-api-key"] = self.current_api_key
                        continue
                    else:
                        # No more API keys available
                        error_msg = f"All API keys have reached their limits. Last error: {response.text}"
                        return None, error_msg
                else:
                    # Non-rate-limit error
                    error_msg = f"API error (status {response.status_code}): {response.text}"
                    return None, error_msg
                    
            except requests.exceptions.RequestException as e:
                print(f"❌ [GEMINI SERVICE] Request exception with API key #{self.current_key_index + 1}: {str(e)}")
                
                # Try to switch to next API key for network issues
                if self._switch_to_next_api_key():
                    headers["X-goog-api-key"] = self.current_api_key
                    continue
                else:
                    return None, f"Network error: {str(e)}"
        
        return None, "Maximum retry attempts exceeded"
        
    def chat(self, messages: List[Dict[str, str]], max_tokens: int = 3000) -> Dict[str, Any]:
        """Send messages to Gemini API and get response with fallback support"""
        try:
            headers = {
                "Content-Type": "application/json",
                "X-goog-api-key": self.current_api_key
            }
            
            # Convert OpenAI format messages to Gemini format
            contents = []
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                
                if role == "system":
                    # For system messages, prepend to user message or handle separately
                    continue
                elif role == "user":
                    contents.append({
                        "parts": [{"text": content}]
                    })
                elif role == "assistant":
                    # Gemini doesn't have assistant role in the same way, so we'll include it as context
                    contents.append({
                        "parts": [{"text": f"Assistant: {content}"}]
                    })
            
            # If we have system message, prepend it to the first user message
            if messages and messages[0].get("role") == "system":
                system_content = messages[0].get("content", "")
                if contents:
                    contents[0]["parts"][0]["text"] = f"{system_content}\n\n{contents[0]['parts'][0]['text']}"
            
            data = {
                "contents": contents
            }
            
            # Make API request with fallback support
            response, error = self._make_api_request(headers, data)
            
            if error:
                return {
                    "success": False,
                    "response": f"Gemini API error: {error}",
                    "error": error
                }
            
            result = response.json()
            
            # Extract content from Gemini response
            if "candidates" in result and result["candidates"]:
                content = result["candidates"][0]["content"]["parts"][0]["text"]
            else:
                content = "No response generated"
            
            print(f"Gemini Response Type: {type(content)}")
            print(f"Gemini Response Content: {content[:200]}...")
            
            # Ensure we return a string, not an object
            if isinstance(content, dict):
                # If Gemini returns a JSON object, convert it to a formatted string
                content = json.dumps(content, indent=2)
            elif not isinstance(content, str):
                content = str(content)
            
            return {
                "success": True,
                "response": content,
                "usage": result.get("usage", {}),
                "api_key_used": f"#{self.current_key_index + 1}"
            }
            
        except Exception as e:
            return {
                "success": False,
                "response": f"Unexpected error: {str(e)}",
                "error": str(e)
            }
    
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
