# openrouter_client.py - Phiên bản "Biệt kích" (Tự động đổi model khi lỗi)
import os
import httpx
import time
import asyncio
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

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

class OpenRouterClient:
    def __init__(self):
        self.api_key = os.getenv('OPENROUTER_API_KEY')
        self.base_url = "https://openrouter.ai/api/v1"
        
        # DANH SÁCH CÁC MODEL MIỄN PHÍ ĐỌC ẢNH TỐT NHẤT
        # Hệ thống sẽ thử lần lượt từ trên xuống dưới
        self.fallback_models = [
            "google/gemini-2.0-flash-exp:free",           # Top 1: Ngon nhất, đọc bảng biểu tốt
            "meta-llama/llama-3.2-11b-vision-instruct:free", # Top 2: Ổn định, ít lỗi
            "google/gemini-2.0-pro-exp-02-05:free",       # Top 3: Thông minh nhưng chậm
            "huggingfaceh4/zephyr-7b-beta:free",          # Chống cháy (Chỉ text, không đọc ảnh)
        ]
        
        self.default_model = self.fallback_models[0]
        
        if not self.api_key:
            print("🔴❌ CẢNH BÁO: Chưa cài đặt OpenRouter API key trong file .env!")
        
        timeout = httpx.Timeout(60.0, read=120.0)
        self.client = httpx.AsyncClient(timeout=timeout)
    
    async def chat_completion(self, messages, model=None, temperature=0.7):
        if not self.api_key:
            return LLMResponse("Lỗi: Chưa có API Key. Hãy kiểm tra file .env", "error", 0, 0)
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:8501",
            "X-Title": "Construction AI Assistant Pro"
        }
        
        # Xử lý tin nhắn
        api_messages = []
        for msg in messages:
            if msg.image_data:
                content_payload = [
                    {"type": "text", "text": msg.content},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{msg.image_data}"
                        }
                    }
                ]
                api_messages.append({"role": msg.role, "content": content_payload})
            else:
                api_messages.append({"role": msg.role, "content": msg.content})
        
        start_time = time.time()
        
        # --- CƠ CHẾ TỰ ĐỘNG THAY ĐỔI MODEL (FALLBACK LOOP) ---
        last_error = ""
        models_to_try = [model] if model else self.fallback_models
        
        for current_model in models_to_try:
            try:
                payload = {
                    "model": current_model,
                    "messages": api_messages,
                    "temperature": temperature
                }
                
                response = await self.client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if 'error' in result:
                        print(f"⚠️ Model {current_model} bị lỗi: {result['error']['message']}")
                        continue 
                        
                    content = result['choices'][0]['message']['content']
                    usage = result.get('usage', {})
                    
                    print(f"✅ Thành công với model: {current_model}")
                    return LLMResponse(
                        content=content,
                        model=current_model,
                        tokens_used=usage.get('total_tokens', 0),
                        response_time=time.time() - start_time
                    )
                else:
                    print(f"⚠️ Model {current_model} gặp lỗi {response.status_code}. Đang đổi model khác...")
                    continue

            except Exception as e:
                print(f"⚠️ Lỗi kết nối với {current_model}: {e}")
                last_error = str(e)
                continue
        
        return LLMResponse(f"❌ Tất cả các model đều bận. Hãy thử lại sau vài giây.", "error", 0, 0)
    
    async def close(self):
        await self.client.aclose()