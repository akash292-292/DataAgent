from schemas import LLMChatRequest, LLMChatResponse

class LLMService:
    """Simple LLM service for basic chat responses"""
    
    def chat(self, request: dict) -> dict:
        """Simple chat response - returns the message as response"""
        try:
            message = request.get("message", "")
            
            return {
                "response": message or "Hello! How can I help you?",
                "is_complete": True,
                "next_question": None
            }
        except Exception as e:
            return {
                "response": f"I encountered an error: {str(e)}. Please try again.",
                "is_complete": False,
                "next_question": None
            }
    
llm_service = LLMService() 