import httpx
import time
from dataclasses import dataclass

@dataclass
class ChatMessage:
    role: str
    content: str
    image_data: str = None

@dataclass
class LLMResponse:
    content: str
    model: str
    tokens_used: int
    response_time: float

class OllamaClient:
    def __init__(self):
        self.base_url = "http://localhost:11434/api/chat"
        self.text_model = "llama3.2" 
        self.vision_model = "llama3.2-vision"
        self.client = httpx.AsyncClient(timeout=120.0)
    
    async def chat_completion(self, messages, model=None, temperature=0.7):
        start_time = time.time()
        has_image = any(msg.image_data for msg in messages)
        selected_model = self.vision_model if has_image else self.text_model
        
        ollama_messages = []
        for msg in messages:
            payload = {"role": msg.role, "content": msg.content}
            if msg.image_data: payload["images"] = [msg.image_data]
            ollama_messages.append(payload)
        
        json_payload = {
            "model": selected_model,
            "messages": ollama_messages,
            "stream": False,
            "options": {"temperature": temperature}
        }
        
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(self.base_url, json=json_payload)
                if response.status_code != 200:
                    return LLMResponse(f"Lỗi: {response.text}", "error", 0, 0)
                result = response.json()
                return LLMResponse(
                    content=result.get('message', {}).get('content', ''),
                    model=selected_model,
                    tokens_used=result.get('eval_count', 0),
                    response_time=time.time() - start_time
                )
        except Exception as e:
            return LLMResponse(f"Lỗi kết nối: {e}", "error", 0, 0)

    async def close(self):
        pass