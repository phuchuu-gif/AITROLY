# app.py - FIXED: Chat thật 100% + Xóa nhiều tài liệu

# =============================================================================
# PYTORCH + STREAMLIT COMPATIBILITY FIX
# =============================================================================
import os
import warnings

# Fix PyTorch warnings
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["PYTHONWARNINGS"] = "ignore::FutureWarning"

try:
    import torch
    torch.classes.__path__ = []
    warnings.filterwarnings("ignore", category=UserWarning, module="torch")
except:
    pass

# =============================================================================
# IMPORTS
# =============================================================================
import streamlit as st
import time
import psutil
import pandas as pd
import tempfile
import uuid
from datetime import datetime
from pathlib import Path

# Custom modules
from database import db_manager
from document_processor import DocumentProcessor

# Enhanced features
try:
    from smart_naming import smart_namer
    from intent_classifier import intent_classifier, ChatIntent
    ENHANCED_FEATURES = True
    print("✅ Tính năng nâng cao đã tải thành công!")
except ImportError as e:
    print(f"⚠️ Tính năng nâng cao không khả dụng: {e}")
    ENHANCED_FEATURES = False
    
    # Fallback classes
    class ChatIntent:
        DOCUMENT_SEARCH = "document_search"
        GENERAL_CHAT = "general_chat"
        GREETING = "greeting"
    
    class FallbackClassifier:
        def classify_intent(self, text):
            return ChatIntent.DOCUMENT_SEARCH if any(word in text.lower() for word in ['tcvn', 'qcvn', 'tìm', 'tra cứu']) else ChatIntent.GENERAL_CHAT
        def get_response_for_intent(self, intent, text=""):
            return "Tôi hiểu! Có gì khác tôi có thể giúp không?"
    
    smart_namer = None
    intent_classifier = FallbackClassifier()

# =============================================================================
# CẤU HÌNH TRANG & KHỞI TẠO
# =============================================================================
st.set_page_config(
    page_title="🤖 AI Tìm kiếm Tài liệu & Chat",
    page_icon="🤖",
    layout="wide"
)

# Khởi tạo document processor
@st.cache_resource
def init_document_processor():
    try:
        processor = DocumentProcessor()
        processor.set_db_manager(db_manager)
        return processor
    except Exception as e:
        st.error(f"Không thể khởi tạo bộ xử lý tài liệu: {e}")
        return None

document_processor = init_document_processor()

# Khởi tạo session state
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'processing_status' not in st.session_state:
    st.session_state.processing_status = {}
if 'smart_filenames' not in st.session_state:
    st.session_state.smart_filenames = {}
if 'selected_docs' not in st.session_state:
    st.session_state.selected_docs = []

# =============================================================================
# HÀM HỖ TRỢ NÂNG CAO
# =============================================================================

def generate_smart_filename(uploaded_file):
    """Tạo tên file thông minh sử dụng phân tích tài liệu"""
    if not ENHANCED_FEATURES or not smart_namer:
        return uploaded_file.name
    
    try:
        # Tạo file tạm thời
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(uploaded_file.name).suffix) as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            tmp_file_path = tmp_file.name
        
        # Trích xuất tên thông minh
        smart_name = smart_namer.extract_smart_name(tmp_file_path)
        
        # Dọn dẹp file tạm
        try:
            os.unlink(tmp_file_path)
        except:
            pass
        
        # Tạo tên file cuối cùng
        original_ext = Path(uploaded_file.name).suffix
        if smart_name and smart_name != "Tài liệu":
            final_name = f"{smart_name}{original_ext}"
            # Lưu mapping để sử dụng sau
            st.session_state.smart_filenames[uploaded_file.name] = final_name
            return final_name
        else:
            return uploaded_file.name
            
    except Exception as e:
        print(f"⚠️ Đặt tên thông minh thất bại: {e}")
        return uploaded_file.name

def update_document_name_in_db(original_filename, smart_filename):
    """Cập nhật tên tài liệu trong database sau khi xử lý"""
    if original_filename == smart_filename:
        return  # Không cần thay đổi
    
    try:
        # Lấy kết nối từ db_manager
        conn = db_manager._safe_get_connection()
        if not conn:
            print("⚠️ Không thể cập nhật tên file - không có kết nối database")
            return
        
        try:
            with conn.cursor() as cur:
                # Cập nhật tên file trong bảng documents
                cur.execute("""
                    UPDATE documents 
                    SET file_name = %s 
                    WHERE file_name = %s
                """, (smart_filename, original_filename))
                
                rows_updated = cur.rowcount
                conn.commit()
                
                if rows_updated > 0:
                    print(f"✅ Đã cập nhật tên file: {original_filename} → {smart_filename}")
                else:
                    print(f"⚠️ Không tìm thấy tài liệu để cập nhật: {original_filename}")
                    
        except Exception as e:
            print(f"❌ Lỗi cập nhật tên file trong database: {e}")
            conn.rollback()
            
    except Exception as e:
        print(f"❌ Lỗi kết nối database khi cập nhật tên file: {e}")
    finally:
        if conn:
            db_manager._safe_put_connection(conn)

def delete_multiple_documents(document_ids, file_names):
    """THÊM MỚI: Xóa nhiều tài liệu cùng lúc"""
    success_count = 0
    failed_count = 0
    error_messages = []
    
    for doc_id, file_name in zip(document_ids, file_names):
        try:
            success = db_manager.delete_document(doc_id)
            if success:
                success_count += 1
            else:
                failed_count += 1
                error_messages.append(f"- {file_name}")
        except Exception as e:
            failed_count += 1
            error_messages.append(f"- {file_name}: {str(e)}")
    
    return {
        "success_count": success_count,
        "failed_count": failed_count,
        "error_messages": error_messages
    }

def delete_all_documents_in_workspace(workspace):
    """THÊM MỚI: Xóa tất cả tài liệu trong workspace"""
    try:
        documents = db_manager.get_documents_from_db(workspace, 1000)  # Lấy tất cả
        
        if not documents:
            return {"success": False, "message": f"Không có tài liệu nào trong '{workspace}'"}
        
        doc_ids = [doc['id'] for doc in documents]
        file_names = [doc['file_name'] for doc in documents]
        
        result = delete_multiple_documents(doc_ids, file_names)
        
        total_docs = len(documents)
        success_count = result["success_count"]
        failed_count = result["failed_count"]
        
        if failed_count == 0:
            return {"success": True, "message": f"✅ Đã xóa thành công tất cả {success_count} tài liệu"}
        else:
            return {"success": True, "message": f"⚠️ Xóa {success_count}/{total_docs} tài liệu. {failed_count} thất bại"}
            
    except Exception as e:
        return {"success": False, "message": f"❌ Lỗi xóa tất cả: {str(e)}"}

def handle_chat_with_intent(user_input):
    """FIXED: Bắt buộc tìm kiếm tài liệu THẬT cho mọi câu hỏi"""
    # LOẠI BỎ HOÀN TOÀN intent classification để tránh fallback
    # Mọi câu hỏi đều đi vào tìm kiếm tài liệu
    return handle_document_search_forced(user_input)

def handle_document_search_forced(user_input):
    """FIXED: BẮT BUỘC tìm kiếm tài liệu THẬT - không có fallback"""
    try:
        workspace = st.session_state.get('search_workspace', 'main')
        
        print(f"🔍 SEARCHING in workspace: {workspace} for query: {user_input}")
        
        # Thực hiện tìm kiếm RAG THẬT - KHÔNG kiểm tra document_count
        search_results, citations = db_manager.rag_search(
            user_input,
            workspace,
            top_k=5
        )
        
        print(f"📊 Search results: {len(search_results)} found")
        
        if search_results and len(search_results) > 0:
            # Tạo phản hồi từ kết quả tìm kiếm THẬT
            response_parts = [f"📚 **Tìm thấy {len(search_results)} kết quả liên quan:**\n"]
            
            for i, result in enumerate(search_results[:3], 1):
                content = result.get('content', '')[:400]  # Tăng độ dài content
                file_name = result.get('file_name', 'Tài liệu không xác định')
                similarity = result.get('similarity_score', 0)
                chunk_index = result.get('chunk_index', 0)
                
                response_parts.append(f"\n**{i}️⃣ {file_name}**")
                response_parts.append(f"   📍 Phần {chunk_index} | 🎯 Độ liên quan: {similarity:.3f}")
                response_parts.append(f"   📄 {content.strip()}")
                if i < 3:  # Không thêm separator cho item cuối
                    response_parts.append(f"   {'─' * 50}")
            
            if len(search_results) > 3:
                response_parts.append(f"\n💡 *Và còn {len(search_results) - 3} kết quả khác có liên quan.*")
            
            response = "\n".join(response_parts)
            
            # Chuẩn bị nguồn tham khảo THẬT
            sources = []
            for result in search_results:
                sources.append({
                    'source': result.get('file_name', 'Không xác định'),
                    'similarity': f"{result.get('similarity_score', 0):.3f}",
                    'content_preview': result.get('content', '')[:300],
                    'chunk_index': result.get('chunk_index', 0)
                })
            
            return response, sources
        else:
            # Kiểm tra xem có tài liệu nào không
            document_count = db_manager.get_document_count(workspace)
            
            if document_count == 0:
                return f"📝 **Chưa có tài liệu nào trong '{workspace}'**\n\n🚀 **Hướng dẫn:**\n1. Vào tab '📤 Tải lên'\n2. Chọn file PDF/DOCX/TXT\n3. Nhấn 'Xử lý tất cả tài liệu'\n4. Quay lại đây để hỏi", []
            else:
                return f"🔍 **Không tìm thấy '{user_input}' trong {document_count} tài liệu**\n\n💡 **Thử:**\n• Từ khóa khác: 'bê tông', 'thép', 'móng'...\n• Mã chuẩn: 'TCVN 4054', 'QCVN 01'...\n• Chủ đề: 'an toàn', 'chất lượng'...\n• Kiểm tra chính tả", []
            
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Search error: {error_msg}")
        return f"❌ **Lỗi tìm kiếm**: {error_msg}\n\n🔧 **Kiểm tra:**\n- Kết nối database\n- Dịch vụ Milvus/Elasticsearch\n- Thử lại sau vài phút", []

# =============================================================================
# HÀM HỖ TRỢ GỐC (NÂNG CẤP)
# =============================================================================

def show_system_dashboard():
    """Bảng điều khiển giám sát hệ thống"""
    st.header("📊 Bảng điều khiển hệ thống")
    
    # Nút làm mới tự động
    if st.button("🔄 Làm mới thống kê"):
        st.rerun()
    
    # Thông số hệ thống
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        try:
            cpu = psutil.cpu_percent(interval=1)
            st.metric("Sử dụng CPU", f"{cpu:.1f}%")
        except:
            st.metric("Sử dụng CPU", "Không có")
    
    with col2:
        try:
            memory = psutil.virtual_memory()
            st.metric("Bộ nhớ", f"{memory.percent:.1f}%")
        except:
            st.metric("Bộ nhớ", "Không có")
    
    with col3:
        try:
            disk = psutil.disk_usage('.')
            st.metric("Ổ cứng", f"{disk.percent:.1f}%")
        except:
            st.metric("Ổ cứng", "Không có")
    
    with col4:
        if ENHANCED_FEATURES:
            st.metric("Tính năng nâng cao", "🟢 Hoạt động")
        else:
            st.metric("Tính năng nâng cao", "🟡 Cơ bản")
    
    # Tình trạng dịch vụ
    st.subheader("🏥 Tình trạng dịch vụ")
    try:
        health = db_manager.health_check()
        health_cols = st.columns(4)
        services = [
            ("PostgreSQL", health.get('postgres', False)),
            ("Elasticsearch", health.get('elasticsearch', False)),
            ("Milvus", health.get('milvus', False)),
            ("Embedder", health.get('embedder', False))
        ]
        
        for i, (name, status) in enumerate(services):
            with health_cols[i]:
                if status:
                    st.success(f"🟢 {name}")
                else:
                    st.error(f"🔴 {name}")
    except Exception as e:
        st.error(f"Lỗi kiểm tra tình trạng: {e}")
    
    # Thống kê RAG
    st.subheader("📈 Thống kê hệ thống RAG")
    try:
        stats = db_manager.get_rag_stats()
        stat_cols = st.columns(3)
        
        with stat_cols[0]:
            st.metric("Tài liệu", stats.get('total_documents', 0))
        with stat_cols[1]:
            st.metric("Phân đoạn", stats.get('total_chunks', 0))
        with stat_cols[2]:
            st.metric("Vector embeddings", stats.get('vector_embeddings', 0))
        
        if all(stats.values()):
            st.success("✅ Tất cả thống kê đã sẵn sàng")
    except Exception as e:
        st.error(f"Lỗi thống kê: {e}")

def handle_file_upload():
    """Xử lý tải lên file - TƯƠNG THÍCH với DocumentProcessor hiện tại"""
    st.header("📤 Tải lên tài liệu")
    
    # Hiển thị trạng thái tính năng nâng cao
    if ENHANCED_FEATURES:
        st.success("✅ **Đặt tên thông minh đang hoạt động** - Tự động trích xuất tên tài liệu từ nội dung")
    else:
        st.info("ℹ️ **Chế độ cơ bản** - Sử dụng tên file gốc")
    
    uploaded_files = st.file_uploader(
        "Chọn files để tải lên",
        accept_multiple_files=True,
        type=['pdf', 'docx', 'txt'],
        help="Hỗ trợ: PDF (có OCR), DOCX, TXT. Đặt tên thông minh sẽ tự động trích xuất tiêu đề tài liệu."
    )
    
    if uploaded_files:
        # Chi tiết file với preview tên thông minh
        st.info(f"📊 Đã chọn {len(uploaded_files)} files")
        
        with st.expander("📄 Chi tiết file & Tên thông minh"):
            for file in uploaded_files:
                file_size_mb = len(file.read()) / (1024 * 1024)
                file.seek(0)  # Reset file pointer
                
                col1, col2 = st.columns([1, 1])
                with col1:
                    st.write(f"**Tên gốc:** {file.name}")
                    st.write(f"**Kích thước:** {file_size_mb:.2f} MB")
                
                with col2:
                    if ENHANCED_FEATURES:
                        smart_name = generate_smart_filename(file)
                        if smart_name != file.name:
                            st.write(f"**Tên thông minh:** 🎯 {smart_name}")
                        else:
                            st.write("**Tên thông minh:** 📄 Giống tên gốc")
                    else:
                        st.write("**Tên thông minh:** Không khả dụng")
                
                st.divider()
        
        # Cài đặt dự án
        col1, col2 = st.columns(2)
        with col1:
            project_name = st.text_input("📋 Tên dự án", "Tải lên Web")
        with col2:
            workspace = st.selectbox("🏢 Không gian làm việc", ["main", "test", "archive"])
        
        # Nút xử lý
        if st.button("🚀 Xử lý tất cả tài liệu", type="primary"):
            if not document_processor:
                st.error("❌ Bộ xử lý tài liệu chưa được khởi tạo")
                return
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            results_container = st.container()
            
            successful_files = 0
            failed_files = 0
            
            for i, uploaded_file in enumerate(uploaded_files):
                # Tạo tên file thông minh để hiển thị
                smart_filename = generate_smart_filename(uploaded_file) if ENHANCED_FEATURES else uploaded_file.name
                
                status_text.text(f"Đang xử lý {smart_filename}... ({i+1}/{len(uploaded_files)})")
                
                # Tạo file tạm thời
                try:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(uploaded_file.name).suffix) as tmp_file:
                        tmp_file.write(uploaded_file.getvalue())
                        tmp_file_path = tmp_file.name
                    
                    # FIXED: Sử dụng signature DocumentProcessor gốc (KHÔNG có tham số custom_filename)
                    result = document_processor.process_document_sync(
                        tmp_file_path,
                        project_name,
                        workspace
                    )
                    
                    # FIXED: Cập nhật tên tài liệu SAU khi xử lý nếu tên thông minh khác
                    if ENHANCED_FEATURES and smart_filename != uploaded_file.name and result.get("success"):
                        update_document_name_in_db(uploaded_file.name, smart_filename)
                    
                    # Hiển thị kết quả
                    with results_container:
                        if result["success"]:
                            if result.get("duplicate"):
                                st.warning(f"🔄 **{smart_filename}**: Đã tồn tại")
                            else:
                                file_info = result.get("file_info", {})
                                chunks = file_info.get("chunks_created", 0)
                                processing_time = file_info.get("processing_time", "Không có")
                                
                                if ENHANCED_FEATURES and smart_filename != uploaded_file.name:
                                    st.success(f"✅ **{smart_filename}** (Thông minh): {chunks} phân đoạn trong {processing_time}")
                                else:
                                    st.success(f"✅ **{smart_filename}**: {chunks} phân đoạn trong {processing_time}")
                                successful_files += 1
                        else:
                            st.error(f"❌ **{smart_filename}**: {result.get('error', 'Lỗi không xác định')}")
                            failed_files += 1
                
                except Exception as e:
                    with results_container:
                        st.error(f"❌ **{uploaded_file.name}**: {str(e)}")
                        failed_files += 1
                
                finally:
                    # Dọn dẹp
                    try:
                        if 'tmp_file_path' in locals():
                            os.unlink(tmp_file_path)
                    except:
                        pass
                
                progress_bar.progress((i + 1) / len(uploaded_files))
            
            # Tóm tắt
            status_text.text("✅ Xử lý hoàn tất!")
            if successful_files > 0:
                st.success(f"🎉 Đã xử lý thành công {successful_files} tài liệu!")
            if failed_files > 0:
                st.error(f"❌ Xử lý thất bại {failed_files} tài liệu")

def show_chat_display():
    """Hiển thị lịch sử chat (KHÔNG CÓ INPUT - hiển thị trong tab)"""
    st.header("💬 Lịch sử trò chuyện")
    
    # Thông báo chat THẬT
    st.success("🔍 **Chat tìm kiếm thật 100%** - Mọi câu hỏi đều tìm kiếm trong tài liệu")
    
    # Cài đặt
    with st.expander("⚙️ Cài đặt chat"):
        col1, col2 = st.columns(2)
        with col1:
            st.session_state.search_workspace = st.selectbox(
                "🔍 Không gian tìm kiếm",
                ["main", "test", "archive"],
                key="chat_workspace_select"
            )
        with col2:
            if st.button("🗑️ Xóa lịch sử chat"):
                st.session_state.messages = []
                st.rerun()
    
    # Hiển thị tin nhắn
    if st.session_state.messages:
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
                
                # Hiển thị nguồn cho trợ lý
                if message["role"] == "assistant" and "sources" in message:
                    if message["sources"]:
                        with st.expander("📚 Nguồn tham khảo"):
                            for i, source in enumerate(message["sources"], 1):
                                st.write(f"**{i}. {source.get('source', 'Không xác định')}**")
                                st.write(f"Độ tương đồng: {source.get('similarity', 'Không có')}")
                                if 'chunk_index' in source:
                                    st.write(f"Phần: {source.get('chunk_index', 0)}")
                                st.write(f"Xem trước: {source.get('content_preview', 'Không có')[:200]}...")
    else:
        st.info("💭 Chưa có lịch sử chat. Hãy đặt câu hỏi bên dưới!")

def show_document_management():
    """FIXED: Quản lý tài liệu với XÓA NHIỀU + XÓA HẾT"""
    st.header("📚 Quản lý tài liệu")
    
    # Điều khiển chính
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        workspace = st.selectbox("🏢 Không gian làm việc", ["main", "test", "archive"], key="doc_mgmt_workspace")
    with col2:
        if st.button("🔄 Làm mới"):
            st.rerun()
    with col3:
        # Thống kê nhanh
        try:
            doc_count = db_manager.get_document_count(workspace)
            chunk_count = db_manager.get_chunk_count(workspace)
            st.metric(f"📊 '{workspace}'", f"{doc_count} docs")
        except:
            st.metric(f"📊 '{workspace}'", "0 docs")
    with col4:
        st.write("")  # Spacing
    
    # Lấy danh sách tài liệu
    try:
        documents = db_manager.get_documents_from_db(workspace, 100)
        
        if documents:
            # Nút hành động hàng loạt
            st.subheader("🛠️ Hành động hàng loạt")
            
            bulk_col1, bulk_col2, bulk_col3 = st.columns(3)
            
            with bulk_col1:
                # Nút chọn tất cả / bỏ chọn tất cả
                if st.button("☑️ Chọn tất cả"):
                    st.session_state.selected_docs = [doc['id'] for doc in documents]
                    st.rerun()
            
            with bulk_col2:
                if st.button("⬜ Bỏ chọn tất cả"):
                    st.session_state.selected_docs = []
                    st.rerun()
            
            with bulk_col3:
                selected_count = len(st.session_state.selected_docs)
                if selected_count > 0:
                    if st.button(f"🗑️ Xóa {selected_count} tài liệu", type="secondary"):
                        st.session_state['confirm_bulk_delete'] = True
            
            # Nút xóa tất cả (nguy hiểm)
            if len(documents) > 0:
                st.divider()
                danger_col1, danger_col2 = st.columns([3, 1])
                with danger_col1:
                    st.warning(f"⚠️ **Vùng nguy hiểm**: Xóa tất cả {len(documents)} tài liệu trong '{workspace}'")
                with danger_col2:
                    if st.button("💥 XÓA HẾT", type="primary"):
                        st.session_state['confirm_delete_all'] = True
            
            # Xử lý confirmation bulk delete
            if st.session_state.get('confirm_bulk_delete', False):
                st.error(f"⚠️ **Xác nhận xóa {len(st.session_state.selected_docs)} tài liệu?**")
                
                conf_col1, conf_col2 = st.columns(2)
                with conf_col1:
                    if st.button("✅ XÁC NHẬN XÓA", key="confirm_bulk_yes"):
                        # Thực hiện xóa hàng loạt
                        selected_docs = [doc for doc in documents if doc['id'] in st.session_state.selected_docs]
                        doc_ids = [doc['id'] for doc in selected_docs]
                        file_names = [doc['file_name'] for doc in selected_docs]
                        
                        with st.spinner("Đang xóa..."):
                            result = delete_multiple_documents(doc_ids, file_names)
                        
                        if result['failed_count'] == 0:
                            st.success(f"✅ Đã xóa thành công {result['success_count']} tài liệu!")
                        else:
                            st.warning(f"⚠️ Xóa {result['success_count']}/{len(selected_docs)}. {result['failed_count']} thất bại")
                            if result['error_messages']:
                                st.error("Lỗi:\n" + "\n".join(result['error_messages']))
                        
                        # Reset states
                        st.session_state.selected_docs = []
                        del st.session_state['confirm_bulk_delete']
                        st.rerun()
                
                with conf_col2:
                    if st.button("❌ HỦY", key="confirm_bulk_no"):
                        del st.session_state['confirm_bulk_delete']
                        st.rerun()
            
            # Xử lý confirmation delete all
            if st.session_state.get('confirm_delete_all', False):
                st.error(f"🚨 **XÁC NHẬN XÓA TẤT CẢ {len(documents)} TÀI LIỆU?**")
                st.warning("⚠️ **Hành động này KHÔNG THỂ HOÀN TÁC!**")
                
                conf_col1, conf_col2 = st.columns(2)
                with conf_col1:
                    if st.button("💀 XÁC NHẬN XÓA HẾT", key="confirm_all_yes"):
                        with st.spinner("Đang xóa tất cả..."):
                            result = delete_all_documents_in_workspace(workspace)
                        
                        if result['success']:
                            st.success(result['message'])
                        else:
                            st.error(result['message'])
                        
                        # Reset states
                        st.session_state.selected_docs = []
                        del st.session_state['confirm_delete_all']
                        st.rerun()
                
                with conf_col2:
                    if st.button("❌ HỦY", key="confirm_all_no"):
                        del st.session_state['confirm_delete_all']
                        st.rerun()
            
            st.divider()
            st.subheader(f"📄 Danh sách tài liệu ({len(documents)})")
            
            # Hiển thị từng tài liệu với checkbox
            for i, doc in enumerate(documents):
                with st.container():
                    col1, col2, col3 = st.columns([0.5, 3.5, 1])
                    
                    with col1:
                        # Checkbox để chọn
                        is_selected = doc['id'] in st.session_state.selected_docs
                        if st.checkbox("", value=is_selected, key=f"check_{doc['id']}_{i}"):
                            if doc['id'] not in st.session_state.selected_docs:
                                st.session_state.selected_docs.append(doc['id'])
                        else:
                            if doc['id'] in st.session_state.selected_docs:
                                st.session_state.selected_docs.remove(doc['id'])
                    
                    with col2:
                        # Thông tin tài liệu
                        file_name = doc["file_name"]
                        if ENHANCED_FEATURES and any(keyword in file_name.upper() for keyword in ['TCVN', 'QCVN', 'TCCS', 'THÔNG TƯ', 'NGHỊ ĐỊNH']):
                            st.write(f"🎯 **{file_name}**")
                        else:
                            st.write(f"📄 **{file_name}**")
                        
                        # Thông tin chi tiết
                        info_cols = st.columns(5)
                        with info_cols[0]:
                            st.caption(f"📂 {doc['file_type']}")
                        with info_cols[1]:
                            st.caption(f"📊 {doc['status']}")
                        with info_cols[2]:
                            st.caption(f"🧩 {doc.get('chunks_created', 0)} phần")
                        with info_cols[3]:
                            size_mb = doc.get('file_size', 0) / (1024*1024) if doc.get('file_size') else 0
                            st.caption(f"💾 {size_mb:.1f}MB")
                        with info_cols[4]:
                            upload_date = doc.get("upload_date")
                            if upload_date:
                                st.caption(f"📅 {upload_date.strftime('%d/%m/%Y')}")
                            else:
                                st.caption("📅 Không có")
                    
                    with col3:
                        # Nút xóa đơn lẻ
                        delete_key = f"delete_single_{doc['id']}_{i}"
                        if st.button("🗑️", key=delete_key, help=f"Xóa {file_name}"):
                            st.session_state[f"confirm_single_delete_{doc['id']}"] = True
                        
                        # Xử lý confirmation đơn lẻ
                        if st.session_state.get(f"confirm_single_delete_{doc['id']}", False):
                            st.warning(f"Xóa '{file_name[:30]}...'?")
                            
                            col_yes, col_no = st.columns(2)
                            with col_yes:
                                if st.button("✅", key=f"yes_single_{doc['id']}_{i}"):
                                    success = db_manager.delete_document(doc['id'])
                                    
                                    if success:
                                        st.success(f"Đã xóa {file_name}")
                                    else:
                                        st.error(f"Lỗi xóa {file_name}")
                                    
                                    del st.session_state[f"confirm_single_delete_{doc['id']}"]
                                    st.rerun()
                            
                            with col_no:
                                if st.button("❌", key=f"no_single_{doc['id']}_{i}"):
                                    del st.session_state[f"confirm_single_delete_{doc['id']}"]
                                    st.rerun()
                    
                    st.divider()
        
        else:
            st.info(f"📝 Không có tài liệu nào trong '{workspace}'")
            st.markdown("**Tải lên tài liệu trong tab 'Tải lên' để bắt đầu!**")
    
    except Exception as e:
        st.error(f"Lỗi tải tài liệu: {e}")

def show_testing_tools():
    """Công cụ kiểm tra và chẩn đoán"""
    st.header("🔬 Công cụ kiểm tra")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🔍 Kiểm tra sức khỏe"):
            with st.spinner("Đang chạy kiểm tra sức khỏe..."):
                try:
                    health = db_manager.health_check()
                    st.json(health)
                    
                    # Tóm tắt
                    services_online = sum(1 for v in health.values() if v)
                    total_services = len(health)
                    
                    if services_online == total_services:
                        st.success(f"✅ Tất cả {total_services} dịch vụ đang hoạt động!")
                    else:
                        st.warning(f"⚠️ {services_online}/{total_services} dịch vụ đang hoạt động")
                
                except Exception as e:
                    st.error(f"Kiểm tra sức khỏe thất bại: {e}")
    
    with col2:
        if st.button("⚡ Test tìm kiếm THẬT"):
            workspace = st.session_state.get('search_workspace', 'main')
            
            with st.spinner("Đang test tìm kiếm THẬT..."):
                try:
                    test_queries = [
                        "tiêu chuẩn xây dựng",
                        "an toàn lao động", 
                        "chất lượng công trình",
                        "TCVN",
                        "bê tông"
                    ]
                    
                    results = []
                    for query in test_queries:
                        start_time = time.time()
                        search_results, citations = db_manager.rag_search(query, workspace, 3)
                        response_time = time.time() - start_time
                        
                        results.append({
                            "Truy vấn": query,
                            "Kết quả": len(search_results),
                            "Thời gian (s)": f"{response_time:.3f}"
                        })
                    
                    df = pd.DataFrame(results)
                    st.dataframe(df, use_container_width=True)
                    
                    # Đánh giá
                    total_results = sum(int(r["Kết quả"]) for r in results)
                    if total_results > 0:
                        st.success(f"✅ Tìm kiếm hoạt động! Tổng {total_results} kết quả")
                    else:
                        st.warning(f"⚠️ Không tìm thấy kết quả nào trong '{workspace}'")
                
                except Exception as e:
                    st.error(f"Test tìm kiếm thất bại: {e}")
    
    # Database tests
    st.subheader("💾 Kiểm tra cơ sở dữ liệu")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📊 Kiểm tra kết nối"):
            try:
                stats = db_manager.get_rag_stats()
                st.success(f"✅ Đã kết nối! {stats.get('total_documents', 0)} tài liệu")
            except Exception as e:
                st.error(f"❌ Kết nối thất bại: {e}")
    
    with col2:
        if st.button("🔍 Test search API"):
            try:
                results, citations = db_manager.rag_search("test", "main", 1)
                st.success(f"✅ Search API OK! {len(results)} kết quả")
            except Exception as e:
                st.error(f"❌ Search API thất bại: {e}")
    
    with col3:
        if st.button("🧠 Kiểm tra embedding"):
            try:
                if db_manager.embedder:
                    test_embedding = db_manager.embedder.encode(["test"])
                    st.success(f"✅ Embeddings OK! Dim: {len(test_embedding[0])}")
                else:
                    st.error("❌ Không có embedder")
            except Exception as e:
                st.error(f"❌ Embedding thất bại: {e}")

# =============================================================================
# ỨNG DỤNG CHÍNH
# =============================================================================

def main():
    """Hàm ứng dụng chính"""
    # Tiêu đề ứng dụng
    st.title("🤖 Trợ lý AI Tài liệu")
    st.markdown("*🔍 **Chat tìm kiếm thật 100%** - Không còn demo!*")
    
    # Chỉ báo trạng thái hệ thống
    try:
        health = db_manager.health_check()
        services_online = sum(1 for v in health.values() if v)
        total_services = len(health)
        
        if services_online == total_services:
            st.success(f"🟢 Tất cả hệ thống hoạt động ({services_online}/{total_services})")
        elif services_online > 0:
            st.warning(f"🟡 Một phần hệ thống hoạt động ({services_online}/{total_services})")
        else:
            st.error(f"🔴 Hệ thống ngoại tuyến ({services_online}/{total_services})")
    except:
        st.error("🔴 Trạng thái hệ thống không xác định")
    
    # Tạo tabs
    tabs = st.tabs([
        "📤 Tải lên", 
        "💬 Lịch sử chat",
        "📚 Tài liệu",
        "🔬 Kiểm tra",
        "📊 Bảng điều khiển"
    ])
    
    # Tab content
    with tabs[0]:
        handle_file_upload()
    
    with tabs[1]:
        show_chat_display()
    
    with tabs[2]:
        show_document_management()
    
    with tabs[3]:
        show_testing_tools()
    
    with tabs[4]:
        show_system_dashboard()

# =============================================================================
# CHAT INPUT THẬT 100%
# =============================================================================

st.divider()
st.subheader("💭 Hỏi về tài liệu")
st.info("🎯 **Mọi câu hỏi đều tìm kiếm THẬT trong tài liệu - không còn demo!**")

# Khởi tạo workspace
if 'search_workspace' not in st.session_state:
    st.session_state.search_workspace = 'main'

# Chat input THẬT 100%
if prompt := st.chat_input("💬 Tìm kiếm thông tin trong tài liệu..."):
    # Thêm tin nhắn người dùng
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Xử lý với tìm kiếm THẬT
    with st.spinner("🔍 Đang tìm kiếm trong tài liệu..."):
        try:
            print(f"🚀 FORCED SEARCH for: {prompt}")
            response, sources = handle_chat_with_intent(prompt)
            
            # Thêm phản hồi
            st.session_state.messages.append({
                "role": "assistant",  
                "content": response,
                "sources": sources
            })
            
            st.rerun()
            
        except Exception as e:
            error_response = f"❌ **Lỗi tìm kiếm**: {str(e)}\n\n🔧 Vui lòng kiểm tra kết nối và thử lại"
            st.session_state.messages.append({
                "role": "assistant",
                "content": error_response,
                "sources": []
            })
            st.rerun()

# Sidebar
with st.sidebar:
    st.header("ℹ️ Thông tin hệ thống")
    
    # Trạng thái
    st.success("🎯 Chat tìm kiếm thật 100%")
    st.success("🗑️ Xóa nhiều tài liệu")
    st.success("💥 Xóa hết workspace")
    
    if ENHANCED_FEATURES:
        st.success("✅ Đặt tên thông minh")
    
    st.divider()
    
    try:
        stats = db_manager.get_rag_stats()
        st.metric("📄 Tài liệu", stats.get('total_documents', 0))
        st.metric("🧩 Phân đoạn", stats.get('total_chunks', 0))
        st.metric("🧠 Embeddings", stats.get('vector_embeddings', 0))
    except:
        st.error("Thống kê không khả dụng")
    
    # Workspace info
    current_workspace = st.session_state.get('search_workspace', 'main')
    try:
        workspace_docs = db_manager.get_document_count(current_workspace)
        st.info(f"📂 **'{current_workspace}'**: {workspace_docs} tài liệu")
    except:
        st.info(f"📂 **'{current_workspace}'**: 0 tài liệu")
    
    st.divider()
    st.caption("🤖 AI Tìm kiếm Tài liệu v2.2")
    st.caption("Chat thật 100% + Xóa hàng loạt")

# =============================================================================
# CHẠY ỨNG DỤNG
# =============================================================================

if __name__ == "__main__":
    try:
        os.makedirs("temp", exist_ok=True)
        os.makedirs("logs", exist_ok=True)
        main()
        
    except Exception as e:
        st.error(f"❌ Lỗi ứng dụng: {e}")
        st.error("Vui lòng kiểm tra cấu hình và các thư viện phụ thuộc")