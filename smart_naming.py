# smart_naming.py - Smart Document Title Extraction
import re
import os
from pathlib import Path

# Import PyMuPDF with fallback
try:
    import fitz  # PyMuPDF
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False
    print("⚠️ PyMuPDF not available. Install: pip install PyMuPDF")

class SmartDocumentNamer:
    def __init__(self):
        # Patterns để nhận diện tài liệu Việt Nam
        self.document_patterns = {
            'tcvn': r'TCVN\s+\d+[:\-]\d+[:\-]\d+',
            'qcvn': r'QCVN\s+\d+[:\-]\d+[\/\-]\w+',
            'tccs': r'TCCS\s+\d+[:\-]\d+[:\-]\d+',
            'thong_tu': r'THÔNG\s+TƯ\s+(?:SỐ\s+)?\d+[\/\-]\d+[\/\-][A-Z\-]+',
            'nghi_dinh': r'NGHỊ\s+ĐỊNH\s+(?:SỐ\s+)?\d+[\/\-]\d+[\/\-][A-Z\-]+',
            'cong_van': r'CÔNG\s+VĂN\s+(?:SỐ\s+)?\d+[\/\-][A-Z\-]+',
            'quyet_dinh': r'QUYẾT\s+ĐỊNH\s+(?:SỐ\s+)?\d+[\/\-]\d+[\/\-][A-Z\-]+',
            'chi_thi': r'CHỈ\s+THỊ\s+(?:SỐ\s+)?\d+[\/\-][A-Z\-]+',
            'huong_dan': r'HƯỚNG\s+DẪN\s+(?:SỐ\s+)?\d+[\/\-][A-Z\-]+',
        }
        
        # Patterns cho tiêu đề chính
        self.title_patterns = [
            r'TIÊU\s+CHUẨN\s+QUỐC\s+GIA\s*([A-ZÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚĂĐĨŨƠƯĂÂÊÔƠƯ\s\-:\/\d]+)',
            r'QUY\s+CHUẨN\s+KỸ\s+THUẬT\s+QUỐC\s+GIA\s*([A-ZÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚĂĐĨŨƠƯĂÂÊÔƠƯ\s\-:\/\d]+)',
            r'TIÊU\s+CHUẨN\s+CƠ\s+SỞ\s*([A-ZÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚĂĐĨŨƠƯĂÂÊÔƠƯ\s\-:\/\d]+)',
        ]
    
    def extract_smart_name(self, file_path, max_pages=2):
        """Trích xuất tên thông minh từ tài liệu"""
        try:
            if not os.path.exists(file_path):
                return self._fallback_name(file_path)
            
            if HAS_PYMUPDF:
                return self._extract_with_pymupdf(file_path, max_pages)
            else:
                return self._extract_simple(file_path)
                
        except Exception as e:
            print(f"⚠️ Smart naming error: {e}")
            return self._fallback_name(file_path)
    
    def _extract_with_pymupdf(self, file_path, max_pages):
        """Trích xuất với PyMuPDF (chính xác nhất)"""
        doc = fitz.open(file_path)
        full_text = ""
        
        # Đọc text từ trang đầu
        for page_num in range(min(max_pages, len(doc))):
            page = doc.load_page(page_num)
            text = page.get_text()
            full_text += text + "\n"
        
        doc.close()
        
        # 1. Tìm mã tài liệu trước
        document_code = self._find_document_code(full_text)
        
        # 2. Tìm tiêu đề chính
        main_title = self._find_main_title(full_text)
        
        # 3. Tạo tên thông minh
        if document_code and main_title:
            smart_name = f"{document_code} - {main_title[:60]}"
        elif document_code:
            smart_name = document_code
        elif main_title:
            smart_name = main_title[:60]
        else:
            smart_name = self._find_fallback_title(full_text)
        
        # Làm sạch tên file
        return self._clean_filename(smart_name)
    
    def _find_document_code(self, text):
        """Tìm mã tài liệu (TCVN, QCVN, v.v.)"""
        for doc_type, pattern in self.document_patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(0).strip()
        return None
    
    def _find_main_title(self, text):
        """Tìm tiêu đề chính của tài liệu"""
        # Thử các patterns tiêu đề
        for pattern in self.title_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                title = match.group(1).strip()
                return self._clean_title(title)
        
        # Tìm dòng có chữ viết hoa nhiều nhất
        lines = text.split('\n')
        best_title = None
        best_score = 0
        
        for line in lines[:25]:  # Chỉ xét 25 dòng đầu
            line = line.strip()
            if len(line) < 10 or len(line) > 150:
                continue
            
            # Tính điểm cho dòng này
            uppercase_ratio = sum(1 for c in line if c.isupper()) / len(line)
            length_score = min(len(line) / 50, 1)  # Ưu tiên độ dài vừa phải
            keyword_score = self._calculate_keyword_score(line)
            
            total_score = uppercase_ratio * 0.4 + length_score * 0.3 + keyword_score * 0.3
            
            if total_score > best_score and total_score > 0.3:
                best_score = total_score
                best_title = line
        
        return self._clean_title(best_title) if best_title else None
    
    def _calculate_keyword_score(self, line):
        """Tính điểm dựa trên từ khóa quan trọng"""
        important_keywords = [
            'TIÊU CHUẨN', 'QUY CHUẨN', 'HƯỚNG DẪN', 'KỸ THUẬT',
            'XÂY DỰNG', 'THIẾT KẾ', 'AN TOÀN', 'CHẤT LƯỢNG',
            'BÊ TÔNG', 'THÉP', 'MÓNG', 'CÔNG TRÌNH'
        ]
        
        line_upper = line.upper()
        score = 0
        for keyword in important_keywords:
            if keyword in line_upper:
                score += 0.1
        
        return min(score, 1.0)
    
    def _find_fallback_title(self, text):
        """Tìm tiêu đề dự phòng nếu không tìm thấy tiêu đề chính"""
        lines = text.split('\n')
        
        # Tìm dòng đầu tiên có ít nhất 15 ký tự và có chữ cái
        for line in lines[:15]:
            line = line.strip()
            if len(line) >= 15 and re.search(r'[a-zA-ZÀ-ỹ]', line):
                return line[:60]
        
        return "Tài liệu kỹ thuật"
    
    def _clean_title(self, title):
        """Làm sạch tiêu đề"""
        if not title:
            return None
        
        # Xóa ký tự đặc biệt thừa
        title = re.sub(r'[^\w\s\-\.\(\)\[\]]', '', title, flags=re.UNICODE)
        title = re.sub(r'\s+', ' ', title).strip()
        
        return title if len(title) > 5 else None
    
    def _extract_simple(self, file_path):
        """Trích xuất đơn giản từ tên file"""
        filename = os.path.basename(file_path)
        name_without_ext = os.path.splitext(filename)[0]
        
        # Tìm patterns trong tên file
        for pattern in self.document_patterns.values():
            match = re.search(pattern, name_without_ext, re.IGNORECASE)
            if match:
                return match.group(0)
        
        return name_without_ext if len(name_without_ext) > 5 else "Tài liệu"
    
    def _fallback_name(self, file_path):
        """Tên dự phòng từ file path"""
        try:
            return os.path.splitext(os.path.basename(file_path))[0]
        except:
            return "Tài liệu"
    
    def _clean_filename(self, filename):
        """Làm sạch tên file để có thể lưu"""
        if not filename:
            return "Tài liệu"
        
        # Xóa ký tự không hợp lệ cho tên file
        filename = re.sub(r'[<>:"/\\|?*]', '', filename)
        filename = re.sub(r'\s+', ' ', filename).strip()
        
        # Giới hạn độ dài
        if len(filename) > 100:
            filename = filename[:100] + "..."
        
        return filename if filename else "Tài liệu"

# Khởi tạo instance global
smart_namer = SmartDocumentNamer()
