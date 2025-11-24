# workspace_ui.py - Workspace User Interface Components
import streamlit as st
import pandas as pd
from datetime import datetime
from typing import List, Dict, Any, Optional

class WorkspaceUI:
    """Giao diện quản lý workspace"""
    
    def __init__(self, workspace_manager):
        self.workspace_manager = workspace_manager
        
        # Predefined colors cho workspace
        self.predefined_colors = {
            "🔵 Xanh dương": "#2196F3",
            "🟢 Xanh lá": "#4CAF50", 
            "🟠 Cam": "#FF9800",
            "🟡 Vàng": "#FFC107",
            "🔴 Đỏ": "#F44336",
            "🟣 Tím": "#9C27B0",
            "🔷 Xanh mint": "#00BCD4",
            "⚫ Xám": "#607D8B",
            "🟤 Nâu": "#795548",
            "🌸 Hồng": "#E91E63"
        }
        
        # Predefined icons
        self.predefined_icons = [
            "📁", "🏗️", "🚗", "💻", "📋", "📊", 
            "🔬", "⚡", "🎯", "🛠️", "📚", "💡",
            "🏭", "🌉", "📱", "⚠️", "📈", "🔍",
            "⚙️", "🎨", "🌟", "🔒", "🌐", "🎪"
        ]
    
    def show_workspace_selector(self, key_suffix="", label="🏢 Chọn Workspace"):
        """Hiển thị selector workspace với style đẹp"""
        workspaces = self.workspace_manager.get_all_workspaces()
        
        if not workspaces:
            st.error("❌ Không thể tải danh sách workspace")
            return None
        
        # Tạo options cho selectbox
        options = {}
        default_index = 0
        
        for i, ws in enumerate(workspaces):
            doc_count = ws.get('document_count', 0)
            chunk_count = ws.get('chunk_count', 0)
            
            if doc_count > 0:
                label_text = f"{ws['icon']} {ws['name']} ({doc_count} docs, {chunk_count} chunks)"
            else:
                label_text = f"{ws['icon']} {ws['name']} (trống)"
            
            options[label_text] = ws['id']
            
            # Set default to 'main' if exists
            if ws['id'] == 'main':
                default_index = i
        
        option_keys = list(options.keys())
        
        selected_label = st.selectbox(
            label,
            option_keys,
            index=default_index,
            key=f"workspace_selector_{key_suffix}",
            help="Chọn workspace để làm việc. Tài liệu và chat sẽ được phân loại theo workspace."
        )
        
        if selected_label:
            selected_id = options[selected_label]
            
            # Hiển thị thông tin workspace đã chọn
            selected_workspace = next((ws for ws in workspaces if ws['id'] == selected_id), None)
            if selected_workspace:
                with st.expander(f"ℹ️ Thông tin workspace '{selected_workspace['name']}'", expanded=False):
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.markdown(f"**📄 Tài liệu:** {selected_workspace.get('document_count', 0)}")
                        st.markdown(f"**🧩 Chunks:** {selected_workspace.get('chunk_count', 0)}")
                    
                    with col2:
                        access_icon = "🔒" if selected_workspace['access_level'] == 'private' else "🌐"
                        st.markdown(f"**🔐 Quyền:** {access_icon} {selected_workspace['access_level']}")
                        st.markdown(f"**📅 Tạo:** {selected_workspace['created_at'].strftime('%d/%m/%Y') if selected_workspace.get('created_at') else 'N/A'}")
                    
                    with col3:
                        # Color preview
                        color = selected_workspace.get('color', '#2196F3')
                        st.markdown(
                            f"""
                            <div style="
                                width: 30px; 
                                height: 30px; 
                                background-color: {color}; 
                                border-radius: 50%; 
                                display: inline-block;
                                border: 2px solid #ddd;
                            "></div>
                            """, 
                            unsafe_allow_html=True
                        )
                        if selected_workspace.get('description'):
                            st.caption(selected_workspace['description'])
            
            return selected_id
        
        return None
    
    def show_workspace_management(self):
        """Hiển thị giao diện quản lý workspace chính"""
        st.header("🏢 Quản lý Workspace")
        st.markdown("*Tổ chức tài liệu theo chủ đề và dự án*")
        
        # Tabs cho các chức năng
        tabs = st.tabs(["📋 Danh sách", "➕ Tạo mới", "📊 Thống kê", "⚙️ Cài đặt"])
        
        with tabs[0]:
            self._show_workspace_list()
        
        with tabs[1]:
            self._show_create_workspace()
            
        with tabs[2]:
            self._show_workspace_statistics()
            
        with tabs[3]:
            self._show_workspace_settings()
    
    def _show_workspace_list(self):
        """Hiển thị danh sách workspace dạng cards"""
        st.subheader("📋 Danh sách Workspace")
        
        workspaces = self.workspace_manager.get_all_workspaces()
        
        if not workspaces:
            st.info("📝 Chưa có workspace nào. Hãy tạo workspace đầu tiên!")
            return
        
        # Filter và sort options
        col1, col2, col3 = st.columns(3)
        
        with col1:
            sort_by = st.selectbox(
                "🔄 Sắp xếp theo",
                ["Tên", "Ngày tạo", "Số tài liệu", "Số chunks"],
                key="workspace_sort"
            )
        
        with col2:
            filter_access = st.selectbox(
                "🔐 Lọc quyền truy cập",
                ["Tất cả", "Private", "Public"],
                key="workspace_filter"
            )
        
        with col3:
            st.metric("📊 Tổng số workspace", len(workspaces))
        
        # Apply filters
        filtered_workspaces = workspaces
        if filter_access != "Tất cả":
            filtered_workspaces = [ws for ws in workspaces if ws['access_level'] == filter_access.lower()]
        
        # Apply sorting
        if sort_by == "Tên":
            filtered_workspaces.sort(key=lambda x: x['name'])
        elif sort_by == "Ngày tạo":
            filtered_workspaces.sort(key=lambda x: x.get('created_at', datetime.min), reverse=True)
        elif sort_by == "Số tài liệu":
            filtered_workspaces.sort(key=lambda x: x.get('document_count', 0), reverse=True)
        elif sort_by == "Số chunks":
            filtered_workspaces.sort(key=lambda x: x.get('chunk_count', 0), reverse=True)
        
        st.divider()
        
        # Hiển thị workspace cards
        cols = st.columns(2)
        
        for i, ws in enumerate(filtered_workspaces):
            with cols[i % 2]:
                self._render_workspace_card(ws, i)
    
    def _render_workspace_card(self, workspace: Dict[str, Any], index: int):
        """Render một workspace card"""
        with st.container():
            # Header với màu nền
            color = workspace.get('color', '#2196F3')
            
            # Card header
            st.markdown(
                f"""
                <div style="
                    background: linear-gradient(135deg, {color}20, {color}10);
                    padding: 1rem;
                    border-radius: 10px 10px 0 0;
                    border-left: 4px solid {color};
                    margin-bottom: 0;
                ">
                    <h3 style="margin: 0; color: {color};">
                        {workspace['icon']} {workspace['name']}
                    </h3>
                </div>
                """, 
                unsafe_allow_html=True
            )
            
            # Card body
            with st.container():
                # Description
                if workspace.get('description'):
                    st.caption(workspace['description'])
                else:
                    st.caption("*Không có mô tả*")
                
                # Stats trong 1 hàng
                stat_cols = st.columns(4)
                with stat_cols[0]:
                    st.metric("📄", workspace.get('document_count', 0), help="Số tài liệu")
                with stat_cols[1]:
                    st.metric("🧩", workspace.get('chunk_count', 0), help="Số chunks")
                with stat_cols[2]:
                    access_icon = "🔒" if workspace['access_level'] == 'private' else "🌐"
                    st.markdown(f"**{access_icon}**")
                    st.caption(workspace['access_level'])
                with stat_cols[3]:
                    created_date = workspace.get('created_at')
                    if created_date:
                        st.markdown("**📅**")
                        st.caption(created_date.strftime('%d/%m'))
                
                # Action buttons
                action_cols = st.columns(4)
                
                with action_cols[0]:
                    if st.button("👁️", key=f"view_{workspace['id']}_{index}", help="Xem chi tiết"):
                        st.session_state[f"view_detail_{workspace['id']}"] = True
                
                with action_cols[1]:
                    if st.button("✏️", key=f"edit_{workspace['id']}_{index}", help="Chỉnh sửa"):
                        st.session_state[f"editing_{workspace['id']}"] = True
                
                with action_cols[2]:
                    if workspace['id'] != 'main':  # Không cho xóa workspace main
                        if st.button("🗑️", key=f"delete_{workspace['id']}_{index}", help="Xóa workspace"):
                            st.session_state[f"confirm_delete_{workspace['id']}"] = True
                    else:
                        st.markdown("🔒")  # Locked icon for main workspace
                
                with action_cols[3]:
                    if st.button("📋", key=f"manage_{workspace['id']}_{index}", help="Quản lý tài liệu"):
                        st.session_state['selected_workspace_docs'] = workspace['id']
                
                # Show details
                if st.session_state.get(f"view_detail_{workspace['id']}", False):
                    self._show_workspace_details(workspace)
                
                # Edit form
                if st.session_state.get(f"editing_{workspace['id']}", False):
                    self._show_edit_workspace_form(workspace)
                
                # Delete confirmation
                if st.session_state.get(f"confirm_delete_{workspace['id']}", False):
                    self._show_delete_confirmation(workspace)
                
                # Document management
                if st.session_state.get('selected_workspace_docs') == workspace['id']:
                    self._show_workspace_documents(workspace)
            
            st.divider()
    
    def _show_workspace_details(self, workspace: Dict[str, Any]):
        """Hiển thị chi tiết workspace"""
        with st.expander(f"📊 Chi tiết '{workspace['name']}'", expanded=True):
            detail_cols = st.columns(2)
            
            with detail_cols[0]:
                st.markdown("**📋 Thông tin cơ bản**")
                st.write(f"🆔 ID: `{workspace['id']}`")
                st.write(f"📝 Tên: {workspace['name']}")
                st.write(f"📄 Mô tả: {workspace.get('description', 'Không có')}")
                st.write(f"🔐 Quyền: {workspace['access_level']}")
            
            with detail_cols[1]:
                st.markdown("**📊 Thống kê**")
                st.write(f"📄 Tài liệu: {workspace.get('document_count', 0)}")
                st.write(f"🧩 Chunks: {workspace.get('chunk_count', 0)}")
                st.write(f"📅 Tạo: {workspace.get('created_at', 'N/A')}")
                st.write(f"🔄 Cập nhật: {workspace.get('updated_at', 'N/A')}")
            
            # Color preview
            color = workspace.get('color', '#2196F3')
            st.markdown("**🎨 Màu sắc**")
            st.markdown(
                f"""
                <div style="
                    width: 100px; 
                    height: 30px; 
                    background-color: {color}; 
                    border-radius: 5px; 
                    display: inline-block;
                    border: 1px solid #ddd;
                    text-align: center;
                    line-height: 30px;
                    color: white;
                    font-weight: bold;
                ">
                    {workspace['icon']} {color}
                </div>
                """, 
                unsafe_allow_html=True
            )
            
            if st.button("❌ Đóng chi tiết", key=f"close_detail_{workspace['id']}"):
                del st.session_state[f"view_detail_{workspace['id']}"]
                st.rerun()
    
    def _show_edit_workspace_form(self, workspace: Dict[str, Any]):
        """Form chỉnh sửa workspace"""
        with st.expander(f"✏️ Chỉnh sửa '{workspace['name']}'", expanded=True):
            with st.form(f"edit_workspace_{workspace['id']}"):
                col1, col2 = st.columns(2)
                
                with col1:
                    # Không cho đổi tên workspace 'main'
                    if workspace['id'] == 'main':
                        st.text_input("📝 Tên", value=workspace['name'], disabled=True, 
                                    help="Không thể đổi tên workspace chính")
                        name = workspace['name']
                    else:
                        name = st.text_input("📝 Tên", value=workspace['name'])
                    
                    description = st.text_area("📄 Mô tả", value=workspace.get('description', ''))
                
                with col2:
                    # Color selection
                    current_color = workspace.get('color', '#2196F3')
                    color_key = None
                    for key, value in self.predefined_colors.items():
                        if value == current_color:
                            color_key = key
                            break
                    
                    if not color_key:
                        color_key = list(self.predefined_colors.keys())[0]
                    
                    color_choice = st.selectbox(
                        "🎨 Màu sắc", 
                        self.predefined_colors.keys(),
                        index=list(self.predefined_colors.keys()).index(color_key)
                    )
                    
                    # Icon selection
                    current_icon = workspace.get('icon', '📁')
                    icon_index = 0
                    if current_icon in self.predefined_icons:
                        icon_index = self.predefined_icons.index(current_icon)
                    
                    icon = st.selectbox(
                        "🎭 Icon", 
                        self.predefined_icons,
                        index=icon_index
                    )
                    
                    access_level = st.selectbox(
                        "🔐 Quyền truy cập",
                        ["private", "public"],
                        index=0 if workspace['access_level'] == 'private' else 1
                    )
                
                # Preview
                if name:
                    st.markdown("### 👀 Xem trước")
                    color_value = self.predefined_colors[color_choice]
                    st.markdown(
                        f"""
                        <div style="
                            background: linear-gradient(135deg, {color_value}20, {color_value}10);
                            padding: 0.5rem;
                            border-radius: 5px;
                            border-left: 4px solid {color_value};
                        ">
                            <strong>{icon} {name}</strong><br>
                            <small>{description or 'Không có mô tả'}</small>
                        </div>
                        """, 
                        unsafe_allow_html=True
                    )
                
                col_submit, col_cancel = st.columns(2)
                
                with col_submit:
                    submitted = st.form_submit_button("💾 Lưu thay đổi", type="primary")
                    
                    if submitted:
                        if not name:
                            st.error("❌ Vui lòng nhập tên workspace")
                        else:
                            result = self.workspace_manager.update_workspace(
                                workspace['id'],
                                name=name,
                                description=description,
                                color=self.predefined_colors[color_choice],
                                icon=icon,
                                access_level=access_level
                            )
                            
                            if result['success']:
                                st.success("✅ Đã cập nhật workspace!")
                                del st.session_state[f"editing_{workspace['id']}"]
                                st.rerun()
                            else:
                                st.error(f"❌ {result['error']}")
                
                with col_cancel:
                    if st.form_submit_button("❌ Hủy"):
                        del st.session_state[f"editing_{workspace['id']}"]
                        st.rerun()
    
    def _show_delete_confirmation(self, workspace: Dict[str, Any]):
        """Confirmation dialog xóa workspace"""
        st.error(f"⚠️ **Xác nhận xóa workspace '{workspace['name']}'?**")
        st.warning("Tất cả tài liệu sẽ được chuyển về workspace 'Chính'")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("✅ Xác nhận xóa", key=f"confirm_del_{workspace['id']}", type="primary"):
                result = self.workspace_manager.delete_workspace(workspace['id'])
                if result['success']:
                    st.success(result['message'])
                    del st.session_state[f"confirm_delete_{workspace['id']}"]
                    st.rerun()
                else:
                    st.error(result['error'])
        
        with col2:
            if st.button("❌ Hủy", key=f"cancel_del_{workspace['id']}"):
                del st.session_state[f"confirm_delete_{workspace['id']}"]
                st.rerun()
    
    def _show_workspace_documents(self, workspace: Dict[str, Any]):
        """Hiển thị tài liệu trong workspace"""
        with st.expander(f"📋 Tài liệu trong '{workspace['name']}'", expanded=True):
            documents = self.workspace_manager.get_documents_by_workspace(workspace['id'])
            
            if documents:
                # Tạo DataFrame để hiển thị đẹp
                doc_data = []
                for doc in documents:
                    doc_data.append({
                        "📄 Tên file": doc['file_name'],
                        "📂 Loại": doc['file_type'],
                        "📊 Trạng thái": doc['status'],
                        "🧩 Chunks": doc.get('chunks_created', 0),
                        "📅 Tải lên": doc['upload_date'].strftime('%d/%m/%Y %H:%M') if doc.get('upload_date') else 'N/A'
                    })
                
                df = pd.DataFrame(doc_data)
                st.dataframe(df, use_container_width=True, hide_index=True)
                
                st.info(f"📊 Tổng cộng: {len(documents)} tài liệu")
            else:
                st.info("📝 Chưa có tài liệu nào trong workspace này")
                st.markdown("Vào tab **Tải lên** để thêm tài liệu mới")
            
            if st.button("❌ Đóng", key=f"close_docs_{workspace['id']}"):
                del st.session_state['selected_workspace_docs']
                st.rerun()
    
    def _show_create_workspace(self):
        """Form tạo workspace mới"""
        st.subheader("➕ Tạo Workspace mới")
        st.markdown("*Tạo workspace để tổ chức tài liệu theo chủ đề hoặc dự án*")
        
        with st.form("create_workspace", clear_on_submit=True):
            col1, col2 = st.columns(2)
            
            with col1:
                name = st.text_input(
                    "📝 Tên Workspace *", 
                    placeholder="VD: Dự án ABC, Khảo sát địa chất...",
                    help="Tên workspace phải duy nhất"
                )
                description = st.text_area(
                    "📄 Mô tả", 
                    placeholder="Mô tả ngắn gọn về workspace này...",
                    help="Mô tả giúp người khác hiểu mục đích sử dụng"
                )
            
            with col2:
                color_choice = st.selectbox("🎨 Màu sắc", self.predefined_colors.keys())
                icon = st.selectbox("🎭 Icon", self.predefined_icons)
                access_level = st.selectbox(
                    "🔐 Quyền truy cập", 
                    ["private", "public"],
                    help="Private: Chỉ bạn truy cập | Public: Mọi người có thể xem"
                )
            
            # Preview
            if name:
                st.markdown("### 👀 Xem trước")
                color_value = self.predefined_colors[color_choice]
                
                col_preview1, col_preview2 = st.columns([1, 3])
                
                with col_preview1:
                    st.markdown(
                        f"""
                        <div style="
                            width: 60px; 
                            height: 60px; 
                            background-color: {color_value}; 
                            border-radius: 50%; 
                            display: flex;
                            align-items: center;
                            justify-content: center;
                            font-size: 24px;
                        ">
                            {icon}
                        </div>
                        """, 
                        unsafe_allow_html=True
                    )
                
                with col_preview2:
                    st.markdown(f"**{name}**")
                    st.caption(description or "Không có mô tả")
                    access_icon = "🔒" if access_level == 'private' else "🌐"
                    st.caption(f"{access_icon} {access_level.title()}")
            
            submitted = st.form_submit_button("🚀 Tạo Workspace", type="primary")
            
            if submitted:
                if not name:
                    st.error("❌ Vui lòng nhập tên workspace")
                elif len(name) < 2:
                    st.error("❌ Tên workspace phải có ít nhất 2 ký tự")
                else:
                    result = self.workspace_manager.create_workspace(
                        name=name,
                        description=description,
                        color=self.predefined_colors[color_choice],
                        icon=icon,
                        access_level=access_level
                    )
                    
                    if result['success']:
                        st.success(f"✅ Đã tạo workspace '{name}' thành công!")
                        st.balloons()  # Celebration effect
                        st.rerun()
                    else:
                        st.error(f"❌ {result['error']}")
    
    def _show_workspace_statistics(self):
        """Hiển thị thống kê workspace"""
        st.subheader("📊 Thống kê Workspace")
        
        workspaces = self.workspace_manager.get_all_workspaces()
        
        if not workspaces:
            st.info("📝 Chưa có workspace để hiển thị thống kê")
            return
        
        # Overall stats
        total_docs = sum(ws.get('document_count', 0) for ws in workspaces)
        total_chunks = sum(ws.get('chunk_count', 0) for ws in workspaces)
        private_count = len([ws for ws in workspaces if ws['access_level'] == 'private'])
        public_count = len([ws for ws in workspaces if ws['access_level'] == 'public'])
        
        # Metrics
        metric_cols = st.columns(4)
        with metric_cols[0]:
            st.metric("🏢 Workspace", len(workspaces))
        with metric_cols[1]:
            st.metric("📄 Tổng tài liệu", total_docs)
        with metric_cols[2]:
            st.metric("🧩 Tổng chunks", total_chunks)
        with metric_cols[3]:
            st.metric("📊 Trung bình docs/workspace", f"{total_docs/len(workspaces):.1f}")
        
        st.divider()
        
        # Charts
        chart_cols = st.columns(2)
        
        with chart_cols[0]:
            st.markdown("**📊 Phân bố tài liệu theo workspace**")
            if total_docs > 0:
                chart_data = []
                for ws in workspaces:
                    if ws.get('document_count', 0) > 0:
                        chart_data.append({
                            'Workspace': f"{ws['icon']} {ws['name']}", 
                            'Documents': ws.get('document_count', 0)
                        })
                
                if chart_data:
                    df_chart = pd.DataFrame(chart_data)
                    st.bar_chart(df_chart.set_index('Workspace')['Documents'])
                else:
                    st.info("Không có tài liệu để hiển thị")
            else:
                st.info("Chưa có tài liệu nào")
        
        with chart_cols[1]:
            st.markdown("**🔐 Phân bố quyền truy cập**")
            access_data = pd.DataFrame({
                'Loại': ['🔒 Private', '🌐 Public'],
                'Số lượng': [private_count, public_count]
            })
            st.bar_chart(access_data.set_index('Loại')['Số lượng'])
        
        st.divider()
        
        # Detailed table
        st.markdown("**📋 Bảng chi tiết**")
        table_data = []
        for ws in workspaces:
            access_icon = "🔒" if ws['access_level'] == 'private' else "🌐"
            table_data.append({
                "Workspace": f"{ws['icon']} {ws['name']}",
                "Mô tả": ws.get('description', '')[:50] + ('...' if len(ws.get('description', '')) > 50 else ''),
                "Tài liệu": ws.get('document_count', 0),
                "Chunks": ws.get('chunk_count', 0),
                "Quyền": f"{access_icon} {ws['access_level']}",
                "Ngày tạo": ws.get('created_at', datetime.now()).strftime('%d/%m/%Y') if ws.get('created_at') else 'N/A'
            })
        
        df_table = pd.DataFrame(table_data)
        st.dataframe(df_table, use_container_width=True, hide_index=True)
    
    def _show_workspace_settings(self):
        """Cài đặt workspace"""
        st.subheader("⚙️ Cài đặt Workspace")
        
        # Migration tools
        with st.expander("🔄 Migration Tools"):
            st.markdown("**📦 Migration tài liệu hiện tại**")
            st.info("Chuyển tất cả tài liệu chưa được phân loại về workspace 'Chính'")
            
            if st.button("🚀 Chạy Migration", type="secondary"):
                with st.spinner("Đang migration..."):
                    success = self.workspace_manager.migrate_existing_documents_to_main()
                    if success:
                        st.success("✅ Migration hoàn thành!")
                        st.rerun()
                    else:
                        st.error("❌ Migration thất bại")
        
        # Bulk operations
        with st.expander("🔧 Bulk Operations"):
            st.markdown("**⚠️ Vùng nguy hiểm**")
            st.warning("Các thao tác dưới đây có thể ảnh hưởng đến nhiều workspace cùng lúc")
            
            if st.button("🗑️ Xóa tất cả workspace trống", type="secondary"):
                st.info("🔮 Tính năng này sẽ được phát triển trong phase tiếp theo")
        
        # Export/Import (placeholder)
        with st.expander("📤 Export/Import"):
            st.markdown("**📋 Export workspace configuration**")
            st.info("🔮 Tính năng Export/Import sẽ có trong Phase 2")
            
            col1, col2 = st.columns(2)
            with col1:
                st.button("📤 Export All Workspaces", disabled=True)
            with col2:
                st.button("📥 Import Workspaces", disabled=True)
        
        # Future features preview
        with st.expander("🔮 Tính năng sắp có"):
            st.markdown("""
            **Phase 2 - File & Media System:**
            - 🔗 Chia sẻ workspace với người khác
            - 👥 Collaborative workspace
            - 📊 Advanced analytics và usage tracking
            
            **Phase 3 - Smart Notes & Document Chat:**
            - 🤖 Auto-categorization documents vào workspace phù hợp
            - 🎨 Custom themes và advanced UI customization
            - 📱 Mobile-responsive workspace management
            
            **Phase 4 - Advanced Search & AI:**
            - 🔍 Cross-workspace universal search
            - 🤖 AI-powered workspace suggestions
            - 📈 Predictive workspace organization
            """)
    
    def show_workspace_quick_stats(self):
        """Hiển thị stats nhanh cho sidebar"""
        workspaces = self.workspace_manager.get_all_workspaces()
        
        if workspaces:
            total_workspaces = len(workspaces)
            total_docs = sum(ws.get('document_count', 0) for ws in workspaces)
            
            st.sidebar.markdown("### 🏢 Workspace Stats")
            st.sidebar.metric("Workspaces", total_workspaces)
            st.sidebar.metric("Tổng tài liệu", total_docs)
            
            # Top workspace
            top_workspace = max(workspaces, key=lambda x: x.get('document_count', 0))
            if top_workspace.get('document_count', 0) > 0:
                st.sidebar.markdown(f"**📊 Top:** {top_workspace['icon']} {top_workspace['name']}")
        
        return workspaces