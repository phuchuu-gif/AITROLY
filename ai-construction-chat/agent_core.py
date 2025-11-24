# agent_core.py - Bộ não xử lý Agentic RAG (Phiên bản Free & Vision)
import asyncio
import json
from typing import List, Dict, Any
import re
from datetime import datetime

# Import thư viện tìm kiếm miễn phí (DuckDuckGo)
try:
    from duckduckgo_search import DDGS
    HAS_DDG = True
except ImportError:
    HAS_DDG = False
    print("⚠️ Chưa cài duckduckgo-search. Chạy: pip install duckduckgo-search")

# Import các module của bạn
from database import db_manager
from openrouter_client import OpenRouterClient, ChatMessage

class ConstructionAgent:
    """
    AI Agent chuyên nghiệp: Sử dụng công cụ MIỄN PHÍ & Mô hình Gemini Flash.
    """
    def __init__(self):
        self.llm_client = OpenRouterClient()
        self.db = db_manager
        
    async def process_query(self, user_query: str, workspace_id: str = "main", image_data: str = None):
        """
        Quy trình xử lý thông minh:
        1. Nhận câu hỏi (và ảnh nếu có)
        2. Lập kế hoạch (Plan)
        3. Dùng công cụ (Act)
        4. Trả lời (Response)
        """
        # BƯỚC 1: LẬP KẾ HOẠCH (PLANNING)
        # Nếu có ảnh, ưu tiên phân tích ảnh trước
        if image_data:
            plan = ["analyze_image"]
        else:
            plan = await self._plan_action(user_query)
        
        print(f"🧠 Agent Plan: {plan}")
        
        context_info = ""
        sources = []
        
        # BƯỚC 2: THỰC THI (ACTING)
        
        # Công cụ 1: Phân tích ảnh (Vision) - Gemini Flash làm cực tốt
        if "analyze_image" in plan and image_data:
            context_info += "\n=== PHÂN TÍCH HÌNH ẢNH ===\n(Người dùng đã gửi kèm một hình ảnh. Hãy phân tích nó chi tiết)\n"

        # Công cụ 2: Tìm trong tài liệu nội bộ (Database)
        if "search_db" in plan:
            print("📂 Đang tìm trong Database...")
            # Tìm kiếm trong kho tài liệu của bạn
            search_results, citations = self.db.rag_search(user_query, workspace_id, top_k=5)
            
            if search_results:
                context_info += "\n=== THÔNG TIN TỪ TÀI LIỆU NỘI BỘ ===\n"
                for res in search_results:
                    # Lấy tên file và nội dung
                    file_name = res.get('file_name', 'Tài liệu')
                    content = res.get('content', '').strip()
                    context_info += f"- [{file_name}]: {content}\n"
                    
                    sources.append({
                        "source": file_name,
                        "content": content[:150] + "...",
                        "type": "Tài liệu nội bộ"
                    })
            else:
                context_info += "\n(Không tìm thấy thông tin trong tài liệu nội bộ)\n"

        # Công cụ 3: Tìm trên Web (DuckDuckGo - Free)
        if "search_web" in plan:
            print("🌐 Đang tìm trên Web (DuckDuckGo)...")
            web_results = self._tool_search_web_free(user_query)
            if web_results:
                context_info += "\n=== THÔNG TIN TỪ WEB (INTERNET) ===\n"
                context_info += web_results + "\n"
                sources.append({
                    "source": "Internet (DuckDuckGo)",
                    "content": "Tổng hợp từ kết quả tìm kiếm web mới nhất.",
                    "type": "Web Search"
                })

        # BƯỚC 3: TỔNG HỢP (SYNTHESIS)
        final_answer = await self._generate_final_response(user_query, context_info, image_data)
        
        return final_answer, sources

    async def _plan_action(self, query: str) -> List[str]:
        """AI tự quyết định dùng công cụ nào dựa trên từ khóa"""
        actions = []
        query_lower = query.lower()
        
        # 1. Từ khóa chuyên môn -> Tìm DB nội bộ
        if any(w in query_lower for w in ['tcvn', 'quy chuẩn', 'tài liệu', 'dự án', 'hồ sơ', 'file', 'trong kho']):
            actions.append("search_db")
            
        # 2. Từ khóa cần thông tin mới/bên ngoài -> Tìm Web
        if any(w in query_lower for w in ['mới nhất', 'giá', 'thị trường', 'google', 'hiện nay', '2024', '2025', 'là ai', 'sự kiện']):
            actions.append("search_web")
            
        # 3. Tính toán
        if any(c.isdigit() for c in query) and any(w in query_lower for w in ['tính', 'nhân', 'chia', 'bao nhiêu']):
            actions.append("calculator")
            
        # Mặc định: Nếu không rõ, tìm cả DB cho chắc ăn
        if not actions:
            actions.append("search_db")
            
        return actions

    def _tool_search_web_free(self, query: str) -> str:
        """Sử dụng DuckDuckGo để tìm kiếm miễn phí"""
        if not HAS_DDG:
            return "Lỗi: Chưa cài module tìm kiếm web."
            
        try:
            results_text = ""
            # Tìm kiếm text thông thường
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=3))
                for res in results:
                    results_text += f"- {res['title']}: {res['body']}\n"
            return results_text if results_text else "Không tìm thấy kết quả trên web."
        except Exception as e:
            print(f"Lỗi search web: {e}")
            return "Không thể truy cập web lúc này (Lỗi mạng hoặc rate limit)."

    async def _generate_final_response(self, query: str, context: str, image_data: str = None):
        """Dùng Gemini Flash để trả lời câu cuối cùng"""
        system_prompt = """Bạn là Trợ lý Xây dựng AI chuyên nghiệp (sử dụng model Gemini Flash).
        Nhiệm vụ: Trả lời câu hỏi người dùng dựa trên thông tin cung cấp.
        
        Quy tắc:
        1. Ưu tiên thông tin từ 'Tài liệu nội bộ' trước.
        2. Nếu nội bộ không có, dùng thông tin 'Web'.
        3. Nếu người dùng gửi ảnh, hãy phân tích kỹ các chi tiết trong ảnh.
        4. Trình bày rõ ràng, chuyên nghiệp (dùng Markdown)."""
        
        user_prompt = f"""Câu hỏi: {query}
        
        Dữ liệu thu thập được:
        {context}
        
        Hãy đưa ra câu trả lời chi tiết:"""
        
        messages = [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=user_prompt, image_data=image_data)
        ]
        
        response = await self.llm_client.chat_completion(messages)
        return response.content

# Khởi tạo Global Agent để dùng bên app
agent_system = ConstructionAgent()