# document_processor.py - Tối ưu tốc độ (Ưu tiên Text gốc)
import os
import uuid
import logging
from pathlib import Path
from typing import Dict, Any, List
import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Thử import các thư viện
try:
    import PyPDF2
except ImportError:
    print("⚠️ Thiếu PyPDF2. Chạy: pip install PyPDF2")

try:
    from paddleocr import PaddleOCR
    from pdf2image import convert_from_path
    PADDLE_AVAILABLE = True
    # Tắt log để chạy nhanh hơn
    paddle_engine = PaddleOCR(use_angle_cls=False, lang='vi', show_log=False) 
    print("✅ PaddleOCR: Sẵn sàng")
except:
    PADDLE_AVAILABLE = False
    print("⚠️ PaddleOCR: Chưa cài đặt (Chỉ đọc được PDF văn bản)")

class DocumentProcessor:
    def __init__(self):
        self.db_manager = None
        self.ocr_enabled = PADDLE_AVAILABLE
    
    def set_db_manager(self, db_manager):
        self.db_manager = db_manager

    def clean_text(self, text):
        if not text: return ""
        return text.replace('\x00', '').strip()

    def _ocr_image_array(self, img_array):
        if not self.ocr_enabled: return ""
        try:
            result = paddle_engine.ocr(img_array, cls=False) # Tắt cls để nhanh hơn
            text = ""
            if result and result[0]:
                for line in result[0]:
                    if line and len(line) > 1:
                        text += line[1][0] + "\n"
            return text
        except: return ""

    def extract_text_from_pdf_smart(self, file_path: str) -> str:
        """Chiến thuật đọc PDF thông minh: Text trước, OCR sau"""
        text_content = ""
        try:
            # BƯỚC 1: ĐỌC NHANH (FAST PATH)
            # Hầu hết file TCVN, QCVN mới đều là dạng này -> Mất < 2 giây
            with open(file_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                num_pages = len(reader.pages)
                extracted_text = ""
                
                for i, page in enumerate(reader.pages):
                    t = page.extract_text()
                    if t: extracted_text += t + "\n"
            
            # Đánh giá chất lượng text lấy được
            # Nếu trung bình mỗi trang có > 50 ký tự có nghĩa -> Đây là file văn bản chuẩn
            avg_chars = len(extracted_text) / num_pages if num_pages > 0 else 0
            
            if avg_chars > 50:
                print(f"🚀 [Fast Mode] Đã đọc được nội dung văn bản ({len(extracted_text)} chars). Bỏ qua OCR.")
                return extracted_text
            
            # BƯỚC 2: ĐỌC CHẬM (SLOW PATH - OCR)
            # Chỉ chạy khi Bước 1 thất bại (File scan, ảnh)
            if self.ocr_enabled:
                print(f"🐢 [Slow Mode] File ít chữ ({avg_chars:.0f} chars/trang). Kích hoạt OCR...")
                images = convert_from_path(file_path) # Cần Poppler
                for i, img in enumerate(images):
                    img_arr = np.array(img)
                    ocr_txt = self._ocr_image_array(img_arr)
                    text_content += f"\n--- Trang {i+1} ---\n{ocr_txt}"
                    print(f"   ✅ OCR xong trang {i+1}")
                return text_content
            else:
                return "[Lỗi] File này là ảnh scan, cần cài đặt PaddleOCR & Poppler để đọc."

        except Exception as e:
            return f"[Lỗi đọc file] {str(e)}"

    def extract_text_from_file(self, file_path: str) -> str:
        ext = Path(file_path).suffix.lower()
        if ext == '.pdf': return self.extract_text_from_pdf_smart(file_path)
        elif ext in ['.docx', '.doc']:
            try:
                import docx
                doc = docx.Document(file_path)
                return "\n".join([p.text for p in doc.paragraphs])
            except: return ""
        elif ext in ['.png', '.jpg']:
            return self._ocr_image_array(file_path) if self.ocr_enabled else ""
        elif ext == '.txt':
            try:
                with open(file_path, 'r', encoding='utf-8') as f: return f.read()
            except: return ""
        return ""

    def split_text_into_chunks(self, text: str, max_chars: int = 1000) -> List[str]:
        if not text: return []
        text = self.clean_text(text)
        chunks = []
        curr = ""
        for para in text.split('\n'):
            if len(curr) + len(para) > max_chars:
                chunks.append(curr)
                curr = para + "\n"
            else:
                curr += para + "\n"
        if curr: chunks.append(curr)
        return chunks

    def process_document_sync(self, file_path: str, project_name: str = "Web Upload", workspace: str = "main") -> Dict[str, Any]:
        try:
            file_name = Path(file_path).name
            file_size = os.path.getsize(file_path)
            doc_id = str(uuid.uuid4())
            
            print(f"📖 Bắt đầu xử lý: {file_name}")
            text_content = self.extract_text_from_file(file_path)
            
            if not text_content or "[Lỗi]" in text_content:
                return {"success": False, "error": text_content if text_content else "Không đọc được nội dung."}

            if self.db_manager:
                self.db_manager.save_document_record({
                    "id": doc_id, "file_name": file_name, "file_size": file_size,
                    "project_name": project_name, "workspace": workspace, "status": "processing"
                })
                
                chunks = self.split_text_into_chunks(text_content)
                saved = 0
                for i, c in enumerate(chunks):
                    data = {
                        'chunk_id': str(uuid.uuid4()), 'document_id': doc_id,
                        'content': c, 'chunk_index': i, 
                        'workspace': workspace, 'project_name': project_name
                    }
                    if self.db_manager.save_chunk_record(data): saved += 1
                
                self.db_manager.update_document_status(doc_id, "completed", f"Đã lưu {saved} đoạn")
                
            return {"success": True, "message": f"Xong! Lưu {saved} đoạn.", "file_info": {"document_id": doc_id}}

        except Exception as e:
            return {"success": False, "error": str(e)}