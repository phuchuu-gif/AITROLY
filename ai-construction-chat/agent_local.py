# agent_local.py - Hỗ trợ chế độ Chat vs Hỏi Tài liệu
import asyncio
from ollama_client import OllamaClient, ChatMessage
from database import db_manager

try:
    from duckduckgo_search import DDGS
    HAS_DDG = True
except ImportError:
    HAS_DDG = False

class LocalConstructionAgent:
    def __init__(self):
        self.llm_client = OllamaClient()
        self.db = db_manager
        
    def _format_history(self, chat_history):
        if not chat_history: return ""
        text = ""
        for msg in chat_history[-4:]: 
            role = "Người dùng" if msg['role'] == 'user' else "Trợ lý"
            content = msg['content'][:500]
            text += f"- {role}: {content}\n"
        return text

    async def process_query(self, user_query: str, workspace_id: str = "main", image_data: str = None, chat_history: list = [], mode: str = "auto"):
        """
        mode: 'auto', 'doc' (Hỏi tài liệu), 'chat' (Tán gẫu)
        """
        plan = []
        
        # 1. Xác định kế hoạch dựa trên MODE
        if image_data: 
            plan.append("analyze_image")
        
        elif mode == "chat":
            # Chế độ tán gẫu: Không tìm DB, không tìm Web
            print("🗣️ Mode: Tán gẫu")
            pass 
            
        elif mode == "doc":
            # Chế độ tài liệu: Bắt buộc tìm DB
            print("📄 Mode: Hỏi tài liệu")
            plan.append("search_db")
            
        else: # Auto mode (Logic cũ)
            q = user_query.lower()
            if any(x in q for x in ['tcvn', 'quy chuẩn', 'tài liệu']): plan.append("search_db")
            elif any(x in q for x in ['giá', 'mới nhất', 'google']) and HAS_DDG: plan.append("search_web")
            else: plan.append("search_db")

        context_info = ""
        sources = []
        
        # 2. Thực thi tìm kiếm
        if "search_db" in plan:
            print("📂 Tìm DB...")
            results, _ = self.db.rag_search(user_query, workspace_id, top_k=3)
            if results:
                context_info += "\n=== TÀI LIỆU NỘI BỘ ===\n"
                for res in results:
                    snip = res.get('content', '')[:200].replace('\n', ' ')
                    context_info += f"- [{res.get('file_name')}]: {snip}...\n"
                    sources.append({"source": res.get('file_name'), "content": snip, "type": "Local DB"})
            else:
                if mode == "doc": 
                    context_info += "\n(Không tìm thấy thông tin nào trong tài liệu của bạn)\n"
        
        if "search_web" in plan and HAS_DDG:
            try:
                with DDGS() as ddgs:
                    web_res = list(ddgs.text(user_query, max_results=2))
                    for w in web_res:
                        context_info += f"- [Web]: {w['body']}\n"
                        sources.append({"source": "Web", "content": w['body'][:100], "type": "Web"})
            except: pass

        # 3. Tổng hợp Prompt
        hist = self._format_history(chat_history)
        
        if mode == "chat" and not context_info:
            # Prompt cho chế độ tán gẫu
            prompt = f"""Bạn là trợ lý AI thân thiện. Hãy trò chuyện với người dùng.
            Lịch sử:
            {hist}
            Câu hỏi: {user_query}"""
        else:
            # Prompt cho chế độ hỏi tài liệu
            prompt = f"""Bạn là trợ lý xây dựng. Dựa vào thông tin sau để trả lời.
            LỊCH SỬ:
            {hist}
            THÔNG TIN THAM KHẢO:
            {context_info}
            CÂU HỎI: {user_query}
            TRẢ LỜI (Tiếng Việt):"""
        
        msg = ChatMessage(role="user", content=prompt, image_data=image_data)
        res = await self.llm_client.chat_completion([msg])
        return res.content, sources

agent_system = LocalConstructionAgent()