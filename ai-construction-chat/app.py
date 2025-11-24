# app.py - PHASE 1 INTEGRATED: Workspace System + Enhanced Chat

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

# PHASE 1: Workspace System
from workspace_manager import WorkspaceManager
from workspace_ui import WorkspaceUI
from chat_session_manager import ChatSessionManager

# Enhanced features (existing)
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
    page_title="🤖 AI Trợ lý v3.0 - Workspace System",
    page_icon="🏢",
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

# PHASE 1: Khởi tạo workspace system
@st.cache_resource
def init_workspace_system():
    try:
        workspace_manager = WorkspaceManager(db_manager)
        workspace_ui = WorkspaceUI(workspace_manager)
        chat_session_manager = ChatSessionManager(db_manager)
        
        # Migration: Chuyển documents hiện tại về workspace main
        workspace_manager.migrate_existing_documents_to_main()
        
        return workspace_manager, workspace_ui, chat_session_manager
    except Exception as e:
        st.error(f"Không thể khởi tạo workspace system: {e}")
        return None, None, None

# Initialize systems
document_processor = init_document_processor()
workspace_manager, workspace_ui, chat_session_manager = init_workspace_system()

# Khởi tạo session state
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'processing_status' not in st.session_state:
    st.session_state.processing_status = {}
if 'smart_filenames' not in st.session_state:
    st.session_state.smart_filenames = {}
if 'selected_docs' not in st.session_state:
    st.session_state.selected_docs = []
if 'current_workspace' not in st.session_state:
    st.session_state.current_workspace = 'main'
if 'current_chat_session' not in st.session_state:
    st.session_state.current_chat_session = None

# =============================================================================
# HÀM HỖ TRỢ NÂNG CAO (EXISTING)
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
        return
    
    try:
        conn = db_manager._safe_get_connection()
        if not conn:
            return
        
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE documents 
                    SET file_name = %s 
                    WHERE file_name = %s
                """, (smart_filename, original_filename))
                
                rows_updated = cur.rowcount
                conn.commit()
                
                if rows_updated > 0:
                    print(f"✅ Đã cập nhật tên file: {original_filename} → {smart_filename}")
                    
        except Exception as e:
            conn.rollback()
            
    except Exception as e:
        print(f"❌ Lỗi kết nối database khi cập nhật tên file: {e}")
    finally:
        if conn:
            db_manager._safe_put_connection(conn)

def handle_chat_with_intent(user_input, workspace_id='main'):
    """ENHANCED: Chat với workspace context"""
    return handle_document_search_in_workspace(user_input, workspace_id)

def handle_document_search_in_workspace(user_input, workspace_id):
    """ENHANCED: Tìm kiếm tài liệu trong workspace cụ thể"""
    try:
        print(f"🔍 SEARCHING in workspace: {workspace_id} for query: {user_input}")
        
        # Thực hiện tìm kiếm RAG với workspace filter
        search_results, citations = db_manager.rag_search(
            user_input,
            workspace_id,  # Sử dụng workspace_id thay vì 'main'
            top_k=5
        )
        
        print(f"📊 Search results: {len(search_results)} found")
        
        if search_results and len(search_results) > 0:
            # Lấy thông tin workspace
            workspace_info = workspace_manager.get_workspace_by_id(workspace_id) if workspace_manager else None
            workspace_name = workspace_info['name'] if workspace_info else workspace_id
            workspace_icon = workspace_info['icon'] if workspace_info else '📁'
            
            # Tạo phản hồi từ kết quả tìm kiếm THẬT
            response_parts = [f"📚 **Tìm thấy {len(search_results)} kết quả trong workspace {workspace_icon} '{workspace_name}':**\n"]
            
            for i, result in enumerate(search_results[:3], 1):
                content = result.get('content', '')[:400]
                file_name = result.get('file_name', 'Tài liệu không xác định')
                similarity = result.get('similarity_score', 0)
                chunk_index = result.get('chunk_index', 0)
                
                response_parts.append(f"\n**{i}️⃣ {file_name}**")
                response_parts.append(f"   📍 Phần {chunk_index} | 🎯 Độ liên quan: {similarity:.3f}")
                response_parts.append(f"   📄 {content.strip()}")
                if i < 3:
                    response_parts.append(f"   {'─' * 50}")
            
            if len(search_results) > 3:
                response_parts.append(f"\n💡 *Và còn {len(search_results) - 3} kết quả khác có liên quan.*")
            
            response = "\n".join(response_parts)
            
            # Chuẩn bị nguồn tham khảo
            sources = []
            for result in search_results:
                sources.append({
                    'source': result.get('file_name', 'Không xác định'),
                    'similarity': f"{result.get('similarity_score', 0):.3f}",
                    'content_preview': result.get('content', '')[:300],
                    'chunk_index': result.get('chunk_index', 0),
                    'workspace': workspace_name
                })
            
            return response, sources
        else:
            # Kiểm tra xem có tài liệu nào không
            documents = workspace_manager.get_documents_by_workspace(workspace_id) if workspace_manager else []
            workspace_info = workspace_manager.get_workspace_by_id(workspace_id) if workspace_manager else None
            workspace_name = workspace_info['name'] if workspace_info else workspace_id
            
            if len(documents) == 0:
                return f"📝 **Chưa có tài liệu nào trong workspace '{workspace_name}'**\n\n🚀 **Hướng dẫn:**\n1. Vào tab '📤 Tải lên'\n2. Chọn workspace '{workspace_name}'\n3. Upload file PDF/DOCX/TXT\n4. Quay lại đây để hỏi", []
            else:
                return f"🔍 **Không tìm thấy '{user_input}' trong {len(documents)} tài liệu của workspace '{workspace_name}'**\n\n💡 **Thử:**\n• Từ khóa khác: 'bê tông', 'thép', 'móng'...\n• Mã chuẩn: 'TCVN 4054', 'QCVN 01'...\n• Chủ đề: 'an toàn', 'chất lượng'...\n• Kiểm tra chính tả", []
            
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Search error: {error_msg}")
        return f"❌ **Lỗi tìm kiếm**: {error_msg}\n\n🔧 **Kiểm tra:**\n- Kết nối database\n- Dịch vụ Milvus/Elasticsearch\n- Thử lại sau vài phút", []

# =============================================================================
# ENHANCED FUNCTIONS WITH WORKSPACE SUPPORT
# =============================================================================

def show_system_dashboard():
    """Bảng điều khiển giám sát hệ thống với workspace stats"""
    st.header("📊 Bảng điều khiển hệ thống")
    
    # Nút làm mới
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
        if workspace_manager:
            workspaces = workspace_manager.get_all_workspaces()
            st.metric("🏢 Workspaces", len(workspaces))
        else:
            st.metric("🏢 Workspaces", "Error")
    
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
    
    # ENHANCED: Thống kê workspace
    st.subheader("🏢 Thống kê Workspace")
    if workspace_manager:
        try:
            workspaces = workspace_manager.get_all_workspaces()
            
            if workspaces:
                # Tổng quan
                total_docs = sum(ws.get('document_count', 0) for ws in workspaces)
                total_chunks = sum(ws.get('chunk_count', 0) for ws in workspaces)
                
                metric_cols = st.columns(3)
                with metric_cols[0]:
                    st.metric("📄 Tổng tài liệu", total_docs)
                with metric_cols[1]:
                    st.metric("🧩 Tổng chunks", total_chunks)
                with metric_cols[2]:
                    st.metric("📊 TB docs/workspace", f"{total_docs/len(workspaces):.1f}")
                
                # Top workspaces
                active_workspaces = [ws for ws in workspaces if ws.get('document_count', 0) > 0]
                if active_workspaces:
                    st.markdown("**🏆 Top Workspaces:**")
                    for ws in sorted(active_workspaces, key=lambda x: x.get('document_count', 0), reverse=True)[:3]:
                        st.write(f"• {ws['icon']} **{ws['name']}**: {ws.get('document_count', 0)} docs, {ws.get('chunk_count', 0)} chunks")
                
            else:
                st.info("Chưa có workspace nào")
        except Exception as e:
            st.error(f"Lỗi thống kê workspace: {e}")

def handle_file_upload():
    """ENHANCED: Upload file với workspace selection"""
    st.header("📤 Tải lên tài liệu")
    
    # PHASE 1: Workspace selector
    if workspace_ui:
        st.markdown("### 🏢 Chọn Workspace")
        selected_workspace = workspace_ui.show_workspace_selector("upload", "📁 Chọn workspace để lưu tài liệu")
        
        if not selected_workspace:
            st.warning("⚠️ Vui lòng chọn workspace để tiếp tục")
            return
    else:
        selected_workspace = 'main'
        st.info("🔧 Workspace system chưa sẵn sàng, sử dụng workspace 'main'")
    
    # Hiển thị trạng thái tính năng nâng cao
    if ENHANCED_FEATURES:
        st.success("✅ **Đặt tên thông minh đang hoạt động** - Tự động trích xuất tên tài liệu từ nội dung")
    else:
        st.info("ℹ️ **Chế độ cơ bản** - Sử dụng tên file gốc")
    
    uploaded_files = st.file_uploader(
        "Chọn files để tải lên",
        accept_multiple_files=True,
        type=['pdf', 'docx', 'txt'],
        help="Hỗ trợ: PDF (có OCR), DOCX, TXT. Tài liệu sẽ được lưu vào workspace đã chọn."
    )
    
    if uploaded_files:
        # Chi tiết file với preview tên thông minh
        st.info(f"📊 Đã chọn {len(uploaded_files)} files cho workspace **{selected_workspace}**")
        
        with st.expander("📄 Chi tiết file & Tên thông minh"):
            for file in uploaded_files:
                file_size_mb = len(file.read()) / (1024 * 1024)
                file.seek(0)
                
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
            project_name = st.text_input("📋 Tên dự án", f"Upload to {selected_workspace}")
        with col2:
            st.text_input("🏢 Workspace", selected_workspace, disabled=True)
        
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
                smart_filename = generate_smart_filename(uploaded_file) if ENHANCED_FEATURES else uploaded_file.name
                
                status_text.text(f"Đang xử lý {smart_filename}... ({i+1}/{len(uploaded_files)})")
                
                try:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(uploaded_file.name).suffix) as tmp_file:
                        tmp_file.write(uploaded_file.getvalue())
                        tmp_file_path = tmp_file.name
                    
                    # Process document
                    result = document_processor.process_document_sync(
                        tmp_file_path,
                        project_name,
                        selected_workspace  # ENHANCED: Sử dụng workspace đã chọn
                    )
                    
                    # Update smart filename
                    if ENHANCED_FEATURES and smart_filename != uploaded_file.name and result.get("success"):
                        update_document_name_in_db(uploaded_file.name, smart_filename)
                    
                    # ENHANCED: Assign to workspace
                    if result.get("success") and workspace_manager:
                        doc_id = result.get("file_info", {}).get("document_id")
                        if doc_id:
                            workspace_manager.assign_document_to_workspace(doc_id, selected_workspace)
                    
                    # Hiển thị kết quả
                    with results_container:
                        if result["success"]:
                            if result.get("duplicate"):
                                st.warning(f"🔄 **{smart_filename}**: Đã tồn tại")
                            else:
                                file_info = result.get("file_info", {})
                                chunks = file_info.get("chunks_created", 0)
                                processing_time = file_info.get("processing_time", "Không có")
                                
                                st.success(f"✅ **{smart_filename}**: {chunks} chunks → workspace '{selected_workspace}' ({processing_time})")
                                successful_files += 1
                        else:
                            st.error(f"❌ **{smart_filename}**: {result.get('error', 'Lỗi không xác định')}")
                            failed_files += 1
                
                except Exception as e:
                    with results_container:
                        st.error(f"❌ **{uploaded_file.name}**: {str(e)}")
                        failed_files += 1
                
                finally:
                    try:
                        if 'tmp_file_path' in locals():
                            os.unlink(tmp_file_path)
                    except:
                        pass
                
                progress_bar.progress((i + 1) / len(uploaded_files))
            
            # Tóm tắt
            status_text.text("✅ Xử lý hoàn tất!")
            if successful_files > 0:
                st.success(f"🎉 Đã xử lý thành công {successful_files} tài liệu vào workspace '{selected_workspace}'!")
                st.balloons()
            if failed_files > 0:
                st.error(f"❌ Xử lý thất bại {failed_files} tài liệu")

def show_enhanced_chat():
    """ENHANCED: Chat với workspace và session management"""
    st.header("💬 Trò chuyện nâng cao")
    
    # PHASE 1: Workspace selector cho chat
    if workspace_ui:
        current_workspace = workspace_ui.show_workspace_selector("chat", "🔍 Chọn workspace để tìm kiếm")
        if current_workspace:
            st.session_state.current_workspace = current_workspace
    else:
        current_workspace = st.session_state.get('current_workspace', 'main')
        st.info(f"🔧 Sử dụng workspace: {current_workspace}")
    
    # ENHANCED: Session management
    if chat_session_manager and workspace_manager:
        with st.expander("📋 Quản lý Chat Sessions", expanded=False):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("➕ Tạo session mới"):
                    result = chat_session_manager.create_session(current_workspace)
                    if result['success']:
                        st.session_state.current_chat_session = result['session']['id']
                        st.success(f"✅ Đã tạo session: {result['session']['title']}")
                        st.rerun()
                    else:
                        st.error(f"❌ {result['error']}")
            
            with col2:
                # Hiển thị session hiện tại
                current_session_id = st.session_state.get('current_chat_session')
                if current_session_id:
                    session = chat_session_manager.get_session_by_id(current_session_id)
                    if session:
                        st.info(f"📝 Session: {session['title'][:30]}...")
                    else:
                        st.warning("Session không tồn tại")
                        st.session_state.current_chat_session = None
                else:
                    st.info("Chưa có session nào")
            
            with col3:
                # Load sessions
                sessions = chat_session_manager.get_sessions_by_workspace(current_workspace, 10)
                if sessions:
                    session_options = {f"{s['title'][:40]}..." if len(s['title']) > 40 else s['title']: s['id'] for s in sessions}
                    selected_session_title = st.selectbox("📜 Load session", [""] + list(session_options.keys()))
                    
                    if selected_session_title and selected_session_title in session_options:
                        selected_session_id = session_options[selected_session_title]
                        if st.button("📂 Load"):
                            st.session_state.current_chat_session = selected_session_id
                            # Load messages vào session state
                            messages = chat_session_manager.get_session_messages(selected_session_id)
                            st.session_state.messages = []
                            for msg in messages:
                                st.session_state.messages.append({
                                    "role": msg['role'],
                                    "content": msg['content'],
                                    "sources": []  # TODO: Load sources from DB
                                })
                            st.success(f"📂 Đã load {len(messages)} tin nhắn")
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
                                st.write(f"📊 Độ tương đồng: {source.get('similarity', 'Không có')}")
                                if 'workspace' in source:
                                    st.write(f"🏢 Workspace: {source['workspace']}")
                                if 'chunk_index' in source:
                                    st.write(f"📍 Phần: {source.get('chunk_index', 0)}")
                                st.write(f"📄 Xem trước: {source.get('content_preview', 'Không có')[:200]}...")
    else:
        st.info("💭 Chưa có lịch sử chat. Hãy đặt câu hỏi bên dưới!")
        
        # Hiển thị thông tin workspace
        if workspace_manager:
            workspace_info = workspace_manager.get_workspace_by_id(current_workspace)
            if workspace_info:
                documents = workspace_manager.get_documents_by_workspace(current_workspace)
                st.info(f"🏢 Bạn đang chat trong workspace **{workspace_info['icon']} {workspace_info['name']}** với {len(documents)} tài liệu")

def show_document_management():
    """ENHANCED: Quản lý tài liệu với workspace integration"""
    st.header("📚 Quản lý tài liệu")
    
    # PHASE 1: Workspace selector
    if workspace_ui:
        selected_workspace = workspace_ui.show_workspace_selector("doc_mgmt", "🏢 Chọn workspace để quản lý")
        
        if not selected_workspace:
            st.warning("⚠️ Vui lòng chọn workspace")
            return
    else:
        selected_workspace = 'main'
        st.info("🔧 Sử dụng workspace mặc định: main")
    
    # Điều khiển chính
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("🔄 Làm mới"):
            st.rerun()
    
    with col2:
        # Bulk operations
        if st.button("🗑️ Xóa nhiều"):
            st.session_state['show_bulk_delete'] = True
    
    with col3:
        # Workspace info
        if workspace_manager:
            workspace_info = workspace_manager.get_workspace_by_id(selected_workspace)
            if workspace_info:
                st.metric(f"{workspace_info['icon']} {workspace_info['name']}", 
                         f"{workspace_info.get('document_count', 0)} docs")
    
    with col4:
        # Move to workspace
        if st.button("↔️ Chuyển workspace"):
            st.session_state['show_move_workspace'] = True
    
    # Lấy danh sách tài liệu
    try:
        if workspace_manager:
            documents = workspace_manager.get_documents_by_workspace(selected_workspace, 100)
        else:
            documents = db_manager.get_documents_from_db(selected_workspace, 100)
        
        if documents:
            # Hiển thị bulk operations
            if st.session_state.get('show_bulk_delete', False):
                st.subheader("🗑️ Xóa nhiều tài liệu")
                
                # Checkbox cho từng document
                selected_for_delete = []
                
                select_all = st.checkbox("☑️ Chọn tất cả")
                
                for doc in documents:
                    checked = select_all or st.checkbox(f"📄 {doc['file_name']}", key=f"bulk_del_{doc['id']}")
                    if checked:
                        selected_for_delete.append(doc)
                
                if selected_for_delete:
                    st.warning(f"⚠️ Sẽ xóa {len(selected_for_delete)} tài liệu")
                    
                    col_confirm, col_cancel = st.columns(2)
                    with col_confirm:
                        if st.button("✅ Xác nhận xóa", type="primary"):
                            deleted_count = 0
                            for doc in selected_for_delete:
                                try:
                                    success = db_manager.delete_document(doc['id'])
                                    if success:
                                        deleted_count += 1
                                except:
                                    pass
                            
                            st.success(f"✅ Đã xóa {deleted_count}/{len(selected_for_delete)} tài liệu")
                            del st.session_state['show_bulk_delete']
                            st.rerun()
                    
                    with col_cancel:
                        if st.button("❌ Hủy"):
                            del st.session_state['show_bulk_delete']
                            st.rerun()
            
            # Hiển thị move workspace
            if st.session_state.get('show_move_workspace', False) and workspace_manager:
                st.subheader("↔️ Chuyển tài liệu sang workspace khác")
                
                target_workspace = workspace_ui.show_workspace_selector("move_target", "🎯 Chọn workspace đích")
                
                if target_workspace and target_workspace != selected_workspace:
                    # Checkbox cho từng document
                    selected_for_move = []
                    
                    select_all = st.checkbox("☑️ Chọn tất cả để chuyển")
                    
                    for doc in documents:
                        checked = select_all or st.checkbox(f"📄 {doc['file_name']}", key=f"bulk_move_{doc['id']}")
                        if checked:
                            selected_for_move.append(doc)
                    
                    if selected_for_move:
                        st.info(f"📋 Sẽ chuyển {len(selected_for_move)} tài liệu sang workspace '{target_workspace}'")
                        
                        col_confirm, col_cancel = st.columns(2)
                        with col_confirm:
                            if st.button("✅ Xác nhận chuyển", type="primary"):
                                moved_count = 0
                                for doc in selected_for_move:
                                    result = workspace_manager.assign_document_to_workspace(doc['id'], target_workspace)
                                    if result['success']:
                                        moved_count += 1
                                
                                st.success(f"✅ Đã chuyển {moved_count}/{len(selected_for_move)} tài liệu")
                                del st.session_state['show_move_workspace']
                                st.rerun()
                        
                        with col_cancel:
                            if st.button("❌ Hủy chuyển"):
                                del st.session_state['show_move_workspace']
                                st.rerun()
                elif target_workspace == selected_workspace:
                    st.warning("⚠️ Workspace đích trùng với workspace hiện tại")
            
            st.divider()
            st.subheader(f"📄 Danh sách tài liệu ({len(documents)})")
            
            # Hiển thị từng tài liệu
            for i, doc in enumerate(documents):
                with st.container():
                    col1, col2, col3 = st.columns([0.5, 3.5, 1])
                    
                    with col1:
                        # Icon theo loại file
                        file_icon = "📄"
                        if doc['file_type'] == 'pdf':
                            file_icon = "📕"
                        elif doc['file_type'] == 'docx':
                            file_icon = "📘"
                        elif doc['file_type'] == 'txt':
                            file_icon = "📝"
                        
                        st.markdown(f"<h3>{file_icon}</h3>", unsafe_allow_html=True)
                    
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
                        # Actions
                        action_cols = st.columns(2)
                        
                        with action_cols[0]:
                            if st.button("📋", key=f"detail_{doc['id']}_{i}", help="Chi tiết"):
                                st.session_state[f"show_detail_{doc['id']}"] = True
                        
                        with action_cols[1]:
                            if st.button("🗑️", key=f"delete_{doc['id']}_{i}", help="Xóa"):
                                st.session_state[f"confirm_delete_{doc['id']}"] = True
                    
                    # Show detail
                    if st.session_state.get(f"show_detail_{doc['id']}", False):
                        with st.expander(f"📋 Chi tiết '{file_name}'", expanded=True):
                            detail_cols = st.columns(2)
                            
                            with detail_cols[0]:
                                st.write(f"🆔 **ID**: `{doc['id']}`")
                                st.write(f"📁 **File**: {doc['file_name']}")
                                st.write(f"📂 **Loại**: {doc['file_type']}")
                                st.write(f"📊 **Trạng thái**: {doc['status']}")
                            
                            with detail_cols[1]:
                                st.write(f"🧩 **Chunks**: {doc.get('chunks_created', 0)}")
                                st.write(f"💾 **Kích thước**: {size_mb:.2f} MB")
                                st.write(f"📅 **Tải lên**: {upload_date.strftime('%d/%m/%Y %H:%M') if upload_date else 'N/A'}")
                                st.write(f"🏢 **Workspace**: {selected_workspace}")
                            
                            if st.button("❌ Đóng", key=f"close_detail_{doc['id']}"):
                                del st.session_state[f"show_detail_{doc['id']}"]
                                st.rerun()
                    
                    # Delete confirmation
                    if st.session_state.get(f"confirm_delete_{doc['id']}", False):
                        st.error(f"⚠️ Xác nhận xóa '{file_name}'?")
                        
                        conf_col1, conf_col2 = st.columns(2)
                        with conf_col1:
                            if st.button("✅ Xóa", key=f"do_delete_{doc['id']}_{i}"):
                                success = db_manager.delete_document(doc['id'])
                                if success:
                                    st.success(f"✅ Đã xóa {file_name}")
                                else:
                                    st.error(f"❌ Lỗi xóa {file_name}")
                                
                                del st.session_state[f"confirm_delete_{doc['id']}"]
                                st.rerun()
                        
                        with conf_col2:
                            if st.button("❌ Hủy", key=f"cancel_delete_{doc['id']}_{i}"):
                                del st.session_state[f"confirm_delete_{doc['id']}"]
                                st.rerun()
                    
                    st.divider()
        
        else:
            st.info(f"📝 Không có tài liệu nào trong workspace '{selected_workspace}'")
            st.markdown("**Vào tab 'Tải lên' để thêm tài liệu mới!**")
    
    except Exception as e:
        st.error(f"Lỗi tải tài liệu: {e}")

# =============================================================================
# ỨNG DỤNG CHÍNH NÂNG CẤP
# =============================================================================

def main():
    """Hàm ứng dụng chính với Phase 1 features"""
    # Tiêu đề ứng dụng
    st.title("🤖 AI Trợ lý v3.0 - Phase 1")
    st.markdown("*🏢 **Workspace System** | 💬 **Enhanced Chat** | 📚 **Smart Document Management***")
    
    # Chỉ báo trạng thái hệ thống
    try:
        health = db_manager.health_check()
        services_online = sum(1 for v in health.values() if v)
        total_services = len(health)
        
        status_col1, status_col2 = st.columns([3, 1])
        
        with status_col1:
            if services_online == total_services:
                st.success(f"🟢 Tất cả hệ thống hoạt động ({services_online}/{total_services})")
            elif services_online > 0:
                st.warning(f"🟡 Một phần hệ thống hoạt động ({services_online}/{total_services})")
            else:
                st.error(f"🔴 Hệ thống ngoại tuyến ({services_online}/{total_services})")
        
        with status_col2:
            # Phase indicator
            if workspace_manager and workspace_ui:
                st.success("🏢 Phase 1: ACTIVE")
            else:
                st.error("🏢 Phase 1: ERROR")
    except:
        st.error("🔴 Trạng thái hệ thống không xác định")
    
    # ENHANCED: Tabs với Phase 1 features
    tabs = st.tabs([
        "📤 Tải lên", 
        "💬 Chat nâng cao",
        "📚 Tài liệu",
        "🏢 Workspace",  # NEW: Phase 1
        "🔬 Kiểm tra",
        "📊 Dashboard"
    ])
    
    # Tab 1: Tải lên tài liệu (ENHANCED)
    with tabs[0]:
        handle_file_upload()
    
    # Tab 2: Chat nâng cao (ENHANCED)
    with tabs[1]:
        show_enhanced_chat()
    
    # Tab 3: Quản lý tài liệu (ENHANCED)
    with tabs[2]:
        show_document_management()
    
    # Tab 4: Workspace Management (NEW)
    with tabs[3]:
        if workspace_ui:
            workspace_ui.show_workspace_management()
        else:
            st.error("❌ Workspace system không khả dụng")
            st.info("Vui lòng kiểm tra workspace_manager.py và workspace_ui.py")
    
    # Tab 5: Kiểm tra (EXISTING)
    with tabs[4]:
        show_testing_tools()
    
    # Tab 6: Dashboard (ENHANCED)
    with tabs[5]:
        show_system_dashboard()

def show_testing_tools():
    """Công cụ kiểm tra với workspace testing"""
    st.header("🔬 Công cụ kiểm tra")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🔍 Kiểm tra sức khỏe"):
            with st.spinner("Đang kiểm tra..."):
                try:
                    health = db_manager.health_check()
                    st.json(health)
                    
                    services_online = sum(1 for v in health.values() if v)
                    total_services = len(health)
                    
                    if services_online == total_services:
                        st.success(f"✅ Tất cả {total_services} dịch vụ hoạt động!")
                    else:
                        st.warning(f"⚠️ {services_online}/{total_services} dịch vụ hoạt động")
                
                except Exception as e:
                    st.error(f"Kiểm tra thất bại: {e}")
    
    with col2:
        if st.button("🏢 Test Workspace System"):
            if workspace_manager and workspace_ui:
                with st.spinner("Đang test workspace..."):
                    try:
                        # Test get workspaces
                        workspaces = workspace_manager.get_all_workspaces()
                        st.success(f"✅ Workspace system OK! {len(workspaces)} workspaces")
                        
                        # Test stats
                        total_docs = sum(ws.get('document_count', 0) for ws in workspaces)
                        st.info(f"📊 Tổng: {total_docs} tài liệu trong {len(workspaces)} workspaces")
                        
                        # Show workspace breakdown
                        for ws in workspaces[:3]:  # Top 3
                            st.write(f"• {ws['icon']} **{ws['name']}**: {ws.get('document_count', 0)} docs")
                    
                    except Exception as e:
                        st.error(f"❌ Test workspace thất bại: {e}")
            else:
                st.error("❌ Workspace system không khả dụng")
    
    # ENHANCED: Test chat with workspace
    st.subheader("💬 Test Chat với Workspace")
    
    if workspace_ui:
        test_workspace = workspace_ui.show_workspace_selector("test_chat", "🧪 Chọn workspace để test")
        test_query = st.text_input("💭 Câu hỏi test", "tiêu chuẩn xây dựng")
        
        if st.button("🚀 Test Chat") and test_query and test_workspace:
            with st.spinner("Đang test chat..."):
                try:
                    response, sources = handle_document_search_in_workspace(test_query, test_workspace)
                    
                    st.markdown("**📄 Kết quả:**")
                    st.markdown(response)
                    
                    if sources:
                        st.markdown(f"**📊 Sources: {len(sources)}**")
                        for i, source in enumerate(sources[:2], 1):
                            st.write(f"{i}. {source.get('source', 'N/A')} (sim: {source.get('similarity', 'N/A')})")
                    
                except Exception as e:
                    st.error(f"❌ Test chat thất bại: {e}")

# =============================================================================
# ENHANCED CHAT INPUT VỚI WORKSPACE
# =============================================================================

st.divider()
st.subheader("💭 Chat với AI Trợ lý")

# Workspace context info
if workspace_manager:
    current_workspace = st.session_state.get('current_workspace', 'main')
    workspace_info = workspace_manager.get_workspace_by_id(current_workspace)
    
    if workspace_info:
        documents = workspace_manager.get_documents_by_workspace(current_workspace)
        st.info(f"🏢 Context: **{workspace_info['icon']} {workspace_info['name']}** | {len(documents)} tài liệu | {workspace_info.get('chunk_count', 0)} chunks")

# Chat input ENHANCED
if prompt := st.chat_input("💬 Hỏi về tài liệu trong workspace hiện tại..."):
    current_workspace = st.session_state.get('current_workspace', 'main')
    current_session = st.session_state.get('current_chat_session')
    
    # Thêm tin nhắn người dùng
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # ENHANCED: Save to session if available
    if chat_session_manager and current_session:
        chat_session_manager.add_message_to_session(current_session, "user", prompt)
    
    # Xử lý với workspace context
    with st.spinner(f"🔍 Đang tìm kiếm trong workspace '{current_workspace}'..."):
        try:
            response, sources = handle_chat_with_intent(prompt, current_workspace)
            
            # Thêm phản hồi
            st.session_state.messages.append({
                "role": "assistant",  
                "content": response,
                "sources": sources
            })
            
            # ENHANCED: Save assistant response to session
            if chat_session_manager and current_session:
                chat_session_manager.add_message_to_session(current_session, "assistant", response)
            
            st.rerun()
            
        except Exception as e:
            error_response = f"❌ **Lỗi tìm kiếm**: {str(e)}\n\n🔧 Vui lòng kiểm tra kết nối và thử lại"
            st.session_state.messages.append({
                "role": "assistant",
                "content": error_response,
                "sources": []
            })
            st.rerun()

# ENHANCED: Sidebar với workspace stats
with st.sidebar:
    st.header("ℹ️ Thông tin hệ thống")
    
    # Phase 1 status
    if workspace_manager and workspace_ui and chat_session_manager:
        st.success("🎯 Phase 1: Workspace System")
        st.success("✅ Workspace Management")
        st.success("✅ Enhanced Chat Sessions")
        st.success("✅ Smart Document Organization")
    else:
        st.error("❌ Phase 1: Lỗi khởi tạo")
    
    if ENHANCED_FEATURES:
        st.success("✅ Đặt tên thông minh")
    
    st.divider()
    
    # ENHANCED: Workspace quick stats
    if workspace_ui:
        workspace_ui.show_workspace_quick_stats()
    
    # Current context
    current_workspace = st.session_state.get('current_workspace', 'main')
    current_session = st.session_state.get('current_chat_session')
    
    st.divider()
    st.markdown("**🔄 Context hiện tại:**")
    st.write(f"🏢 Workspace: `{current_workspace}`")
    if current_session:
        st.write(f"💬 Session: `{current_session[:8]}...`")
    else:
        st.write("💬 Session: *Chưa có*")
    
    st.divider()
    st.caption("🤖 AI Trợ lý v3.0 - Phase 1")
    st.caption("Workspace System | Enhanced Chat | Smart Management")

# =============================================================================
# CHẠY ỨNG DỤNG
# =============================================================================

if __name__ == "__main__":
    try:
        # Đảm bảo thư mục tồn tại
        os.makedirs("temp", exist_ok=True)
        os.makedirs("logs", exist_ok=True)
        
        # Chạy ứng dụng với Phase 1 features
        main()
        
    except Exception as e:
        st.error(f"❌ Lỗi ứng dụng: {e}")
        st.error("Vui lòng kiểm tra cấu hình và các dependencies")
        
        # Enhanced troubleshooting
        with st.expander("🔧 Khắc phục sự cố Phase 1"):
            st.markdown("""
            **🏢 Workspace System Issues:**
            1. Kiểm tra `workspace_manager.py`, `workspace_ui.py` trong cùng thư mục
            2. Đảm bảo PostgreSQL database đang chạy
            3. Kiểm tra bảng `workspaces` đã được tạo
            
            **💬 Chat Session Issues:**
            1. Kiểm tra `chat_session_manager.py` có sẵn
            2. Bảng `chat_sessions` cần được tạo tự động
            3. Cột `session_id` trong bảng `messages`
            
            **📚 Document Management:**
            1. Cột `workspace_id` trong bảng `documents`
            2. Index database cho performance
            3. Foreign key constraints
            
            **🔧 General:**
            1. `pip install streamlit pandas psycopg2-binary`
            2. Backup database trước khi chạy migration
            3. Kiểm tra logs trong console
            """)