# app_local_pro.py - Thêm lựa chọn Mode Chat
import streamlit as st
import asyncio
import base64
import os
import tempfile
import time
from pathlib import Path

# --- IMPORT HỆ THỐNG ---
try:
    from agent_local import agent_system
except ImportError:
    st.error("❌ Lỗi: Thiếu file 'agent_local.py'.")
    st.stop()

from database import db_manager
from document_processor import DocumentProcessor
from workspace_manager import WorkspaceManager
from workspace_ui import WorkspaceUI
from chat_session_manager import ChatSessionManager

# --- CẤU HÌNH TRANG ---
st.set_page_config(
    page_title="🏗️ AI Trợ Lý Xây Dựng (Local)",
    page_icon="🏗️",
    layout="wide"
)

# --- KHỞI TẠO ---
@st.cache_resource
def init_systems():
    try:
        doc_proc = DocumentProcessor()
        doc_proc.set_db_manager(db_manager)
        ws_mgr = WorkspaceManager(db_manager)
        ws_ui = WorkspaceUI(ws_mgr)
        chat_mgr = ChatSessionManager(db_manager)
        ws_mgr.migrate_existing_documents_to_main()
        return doc_proc, ws_mgr, ws_ui, chat_mgr
    except Exception as e:
        st.error(f"Lỗi khởi tạo: {e}")
        return None, None, None, None

document_processor, workspace_manager, workspace_ui, chat_session_manager = init_systems()

# Session State
if 'messages' not in st.session_state: st.session_state.messages = []
if 'current_workspace' not in st.session_state: st.session_state.current_workspace = 'main'
# Thêm state cho mode chat
if 'chat_mode' not in st.session_state: st.session_state.chat_mode = "doc" 

# --- HÀM XỬ LÝ ---
def handle_local_chat(prompt, workspace, image_data=None, mode="doc"):
    """Chạy Agent Local với Mode"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Lấy lịch sử
    history = []
    if 'messages' in st.session_state:
        history = st.session_state.messages[:-1][-5:]
        
    response, sources = loop.run_until_complete(
        agent_system.process_query(prompt, workspace, image_data, chat_history=history, mode=mode)
    )
    loop.close()
    return response, sources

def process_upload(uploaded_file, project_name):
    with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{uploaded_file.name}") as tmp:
        tmp.write(uploaded_file.getvalue())
        tmp_path = tmp.name
    
    try:
        result = document_processor.process_document_sync(
            tmp_path, project_name, st.session_state.current_workspace
        )
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        if os.path.exists(tmp_path): os.unlink(tmp_path)

# --- MAIN UI ---
def main():
    # 1. SIDEBAR
    with st.sidebar:
        st.header("🎛️ Điều khiển")
        if workspace_ui:
            ws = workspace_ui.show_workspace_selector("sidebar", "📁 Workspace")
            if ws: st.session_state.current_workspace = ws
        
        st.divider()
        st.header("📤 Tải lên nhanh")
        uploaded_files = st.file_uploader("Chọn file PDF/DOCX", accept_multiple_files=True)
        if uploaded_files and st.button("🚀 Xử lý"):
            bar = st.progress(0)
            for i, file in enumerate(uploaded_files):
                st.toast(f"Đang đọc: {file.name}...")
                res = process_upload(file, "Quick Upload")
                if res['success']: st.success(f"✅ {file.name}")
                else: st.error(f"❌ {file.name}: {res['error']}")
                bar.progress((i + 1) / len(uploaded_files))
            time.sleep(1)
            st.rerun()

    st.title("🏗️ AI Trợ Lý Xây Dựng (Local)")

    tab1, tab2, tab3 = st.tabs(["💬 Chat & Vision", "📚 Quản lý Tài liệu", "📊 Trạng thái"])

    # --- TAB 1: CHAT ---
    with tab1:
        # THANH CÔNG CỤ CHAT
        c1, c2 = st.columns([3, 1])
        with c1:
            # Chọn chế độ Chat
            mode = st.radio(
                "Chế độ:", 
                ["📄 Hỏi Tài liệu", "💬 Nói chuyện phiếm"], 
                horizontal=True,
                key="mode_radio",
                help="Hỏi Tài liệu: AI sẽ tìm trong kho dữ liệu. Nói chuyện phiếm: AI trả lời tự do."
            )
            # Map giá trị ra code
            st.session_state.chat_mode = "doc" if mode == "📄 Hỏi Tài liệu" else "chat"
            
        with c2:
            if st.button("🧹 Xóa Chat"):
                st.session_state.messages = []
                st.rerun()

        # Vision Upload
        with st.expander("📸 Gửi ảnh/Sơ đồ cho AI xem", expanded=False):
            uploaded_img = st.file_uploader("Chọn ảnh...", type=['png', 'jpg'], key="chat_img")
            image_b64 = None
            if uploaded_img:
                st.image(uploaded_img, width=200)
                try: image_b64 = base64.b64encode(uploaded_img.getvalue()).decode('utf-8')
                except: pass

        # Chat History
        chat_container = st.container()
        with chat_container:
            for msg in st.session_state.messages:
                with st.chat_message(msg["role"]):
                    if msg.get("image_data"):
                        try: st.image(base64.b64decode(msg["image_data"]), width=300)
                        except: pass
                    st.markdown(msg["content"])
                    if msg.get("sources"):
                        with st.expander("🔍 Nguồn tham khảo"):
                            for s in msg["sources"]:
                                st.markdown(f"- **{s['type']}**: {s['source']}")

        # Input Chat
        placeholder = "Hỏi về quy chuẩn, thông số kỹ thuật..." if st.session_state.chat_mode == "doc" else "Trò chuyện tự do..."
        if prompt := st.chat_input(placeholder):
            st.session_state.messages.append({"role": "user", "content": prompt, "image_data": image_b64})
            st.rerun()

        # Xử lý
        if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
            last_msg = st.session_state.messages[-1]
            with st.chat_message("assistant"):
                with st.spinner("Ollama đang suy nghĩ..."):
                    try:
                        res, src = handle_local_chat(
                            last_msg["content"], 
                            st.session_state.current_workspace, 
                            last_msg.get("image_data"),
                            mode=st.session_state.chat_mode
                        )
                        st.markdown(res)
                        if src:
                            with st.expander("🔍 Nguồn tham khảo"):
                                for s in src:
                                    st.markdown(f"- **{s['type']}**: {s['source']}")
                        
                        st.session_state.messages.append({
                            "role": "assistant", "content": res, "sources": src
                        })
                    except Exception as e:
                        st.error(f"Lỗi: {e}")

    # --- TAB 2: TÀI LIỆU ---
    with tab2:
        st.header("Danh sách tài liệu")
        if st.button("🔄 Làm mới"): st.rerun()
        try:
            docs = db_manager.get_documents_from_db(st.session_state.current_workspace, 50)
            if docs:
                for d in docs:
                    with st.expander(f"📄 {d['file_name']} ({d['status']})"):
                        if st.button("Xóa", key=f"del_{d['id']}"):
                            db_manager.delete_document(d['id'])
                            st.rerun()
            else: st.info("Trống.")
        except: st.error("Lỗi kết nối DB")

    # --- TAB 3: TRẠNG THÁI ---
    with tab3:
        st.json(db_manager.health_check())

if __name__ == "__main__":
    main()