# intent_classifier.py - Chat Intent Classification
import re
from enum import Enum

class ChatIntent(Enum):
    DOCUMENT_SEARCH = "document_search"
    GENERAL_CHAT = "general_chat"
    GREETING = "greeting"
    THANKS = "thanks"
    SYSTEM_QUESTION = "system_question"

class ChatIntentClassifier:
    def __init__(self):
        # Keywords cho tìm kiếm tài liệu
        self.document_keywords = [
            'tcvn', 'qcvn', 'tccs', 'tiêu chuẩn', 'quy chuẩn',
            'tài liệu', 'văn bản', 'tra cứu', 'tìm kiếm', 'kiểm tra',
            'xem', 'tham khảo', 'quy định', 'điều khoản', 'hướng dẫn',
            'thông tư', 'nghị định', 'công văn', 'kỹ thuật', 'xây dựng'
        ]
        
        # Patterns cho các loại intent
        self.patterns = {
            ChatIntent.GREETING: [
                r'^(?:xin chào|hello|hi|chào|hey)(?:\s|!|\.)*$',
                r'^(?:chào bạn|chào anh|chào chị)(?:\s|!|\.)*$',
            ],
            
            ChatIntent.THANKS: [
                r'^(?:cảm ơn|cám ơn|thank you|thanks)(?:\s|!|\.)*$',
                r'cảm ơn.*(?:nhiều|lắm)',
            ],
            
            ChatIntent.DOCUMENT_SEARCH: [
                r'(?:tìm|tra cứu|kiểm tra|xem|tham khảo).+(?:tcvn|qcvn|tiêu chuẩn|tài liệu)',
                r'(?:theo|dựa trên|căn cứ).+(?:tcvn|qcvn|tiêu chuẩn)',
                r'tcvn\s+\d+',
                r'qcvn\s+\d+',
                r'(?:quy định|điều khoản).+(?:về|cho|của)',
            ],
            
            ChatIntent.SYSTEM_QUESTION: [
                r'(?:hệ thống|system|app|ứng dụng).+(?:như thế nào|hoạt động|làm việc)',
                r'(?:bạn|ai|gì).+(?:là gì|hoạt động)',
                r'(?:cách|làm sao).+(?:sử dụng|dùng)',
            ],
            
            ChatIntent.GENERAL_CHAT: [
                r'(?:bạn.*(?:khỏe|thế nào|ra sao))',
                r'(?:thời tiết|weather)',
                r'(?:hôm nay|ngày mai)',
                r'^(?:tôi|mình).+(?:muốn|cần|thích)',
            ]
        }
    
    def classify_intent(self, user_input):
        """Phân loại ý định người dùng"""
        if not user_input or not user_input.strip():
            return ChatIntent.GENERAL_CHAT
        
        text = user_input.lower().strip()
        
        # 1. Kiểm tra greeting (ưu tiên cao nhất)
        if self._match_patterns(text, ChatIntent.GREETING):
            return ChatIntent.GREETING
        
        # 2. Kiểm tra thanks
        if self._match_patterns(text, ChatIntent.THANKS):
            return ChatIntent.THANKS
        
        # 3. Kiểm tra có từ khóa tài liệu không
        has_doc_keywords = any(keyword in text for keyword in self.document_keywords)
        
        # 4. Kiểm tra patterns tìm kiếm tài liệu
        if has_doc_keywords or self._match_patterns(text, ChatIntent.DOCUMENT_SEARCH):
            return ChatIntent.DOCUMENT_SEARCH
        
        # 5. Kiểm tra câu hỏi về hệ thống
        if self._match_patterns(text, ChatIntent.SYSTEM_QUESTION):
            return ChatIntent.SYSTEM_QUESTION
        
        # 6. Kiểm tra general chat
        if self._match_patterns(text, ChatIntent.GENERAL_CHAT):
            return ChatIntent.GENERAL_CHAT
        
        # 7. Mặc định: nếu có từ khóa tài liệu thì search, không thì chat
        return ChatIntent.DOCUMENT_SEARCH if has_doc_keywords else ChatIntent.GENERAL_CHAT
    
    def _match_patterns(self, text, intent):
        """Kiểm tra text có khớp với patterns của intent không"""
        if intent not in self.patterns:
            return False
        
        for pattern in self.patterns[intent]:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False
    
    def get_response_for_intent(self, intent, user_input=""):
        """Tạo phản hồi phù hợp cho từng intent"""
        responses = {
            ChatIntent.GREETING: [
                "👋 Xin chào! Tôi là trợ lý AI giúp bạn tra cứu tài liệu kỹ thuật TCVN/QCVN và trò chuyện thông thường.",
                "🌟 Chào bạn! Tôi có thể giúp bạn tìm kiếm tài liệu hoặc trò chuyện về nhiều chủ đề khác.",
                "🚀 Hello! Tôi sẵn sàng hỗ trợ bạn với tài liệu kỹ thuật hoặc chat thông thường."
            ],
            
            ChatIntent.THANKS: [
                "😊 Không có gì! Tôi rất vui được giúp bạn.",
                "🎉 Rất vui khi có thể hỗ trợ bạn!",
                "✨ Cảm ơn bạn! Có gì khác tôi có thể giúp không?"
            ],
            
            ChatIntent.SYSTEM_QUESTION: [
                "🤖 Tôi là hệ thống RAG (Retrieval-Augmented Generation) giúp tìm kiếm và trả lời dựa trên tài liệu đã tải lên.",
                "📚 Hệ thống của tôi hoạt động bằng cách phân tích tài liệu, tạo embeddings và tìm kiếm thông tin liên quan để trả lời câu hỏi.",
                "⚙️ Tôi sử dụng AI để hiểu câu hỏi và tìm thông tin chính xác từ cơ sở dữ liệu tài liệu của bạn."
            ],
            
            ChatIntent.GENERAL_CHAT: [
                "💬 Đây là câu hỏi thú vị! Tôi có thể trò chuyện với bạn về chủ đề này.",
                "🤔 Tôi hiểu bạn muốn chat thông thường. Bạn muốn nói về gì?",
                "😊 Tôi sẵn sàng trò chuyện! Có gì bạn muốn chia sẻ không?"
            ]
        }
        
        import random
        return random.choice(responses.get(intent, ["Tôi hiểu rồi! Có gì khác tôi có thể giúp không?"]))

# Khởi tạo instance global
intent_classifier = ChatIntentClassifier()
