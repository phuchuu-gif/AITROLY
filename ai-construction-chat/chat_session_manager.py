# chat_session_manager.py - Enhanced Chat Session Management
import uuid
import json
from datetime import datetime
from typing import List, Dict, Any, Optional

class ChatSessionManager:
    """Quản lý chat sessions với workspace integration"""
    
    def __init__(self, db_manager):
        self.db = db_manager
        self._create_chat_tables()
    
    def _create_chat_tables(self):
        """Tạo bảng chat sessions và cập nhật schema"""
        conn = self.db._safe_get_connection()
        if not conn:
            print("❌ Không thể kết nối database để tạo chat tables")
            return False
        
        try:
            with conn.cursor() as cur:
                # Tạo bảng chat_sessions
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS chat_sessions (
                        id VARCHAR(100) PRIMARY KEY,
                        workspace_id VARCHAR(100),
                        title VARCHAR(300),
                        summary TEXT,
                        message_count INTEGER DEFAULT 0,
                        last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        is_pinned BOOLEAN DEFAULT FALSE,
                        session_type VARCHAR(50) DEFAULT 'general',
                        metadata JSONB DEFAULT '{}',
                        FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE SET NULL
                    )
                """)
                
                # Kiểm tra và thêm cột session_id vào bảng messages (nếu chưa có)
                cur.execute("""
                    DO $$ 
                    BEGIN
                        BEGIN
                            ALTER TABLE messages ADD COLUMN session_id VARCHAR(100);
                        EXCEPTION
                            WHEN duplicate_column THEN 
                                -- Column already exists, do nothing
                        END;
                    END $$;
                """)
                
                # Thêm cột message_type nếu chưa có
                cur.execute("""
                    DO $$ 
                    BEGIN
                        BEGIN
                            ALTER TABLE messages ADD COLUMN message_type VARCHAR(50) DEFAULT 'text';
                        EXCEPTION
                            WHEN duplicate_column THEN 
                                -- Column already exists, do nothing
                        END;
                    END $$;
                """)
                
                # Thêm index cho performance
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_chat_sessions_workspace_id 
                    ON chat_sessions(workspace_id);
                """)
                
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_messages_session_id 
                    ON messages(session_id);
                """)
                
                conn.commit()
                print("✅ Chat session tables created successfully")
                return True
                
        except Exception as e:
            print(f"❌ Lỗi tạo chat session tables: {e}")
            conn.rollback()
            return False
        finally:
            self.db._safe_put_connection(conn)
    
    def create_session(self, workspace_id: str, title: str = None, 
                      session_type: str = "general") -> Dict[str, Any]:
        """Tạo chat session mới"""
        try:
            session_id = f"chat_{str(uuid.uuid4())[:12]}"
            auto_title = title or f"Chat {datetime.now().strftime('%d/%m %H:%M')}"
            
            conn = self.db._safe_get_connection()
            if not conn:
                return {"success": False, "error": "Không thể kết nối database"}
            
            try:
                with conn.cursor() as cur:
                    # Kiểm tra workspace tồn tại
                    cur.execute("SELECT COUNT(*) FROM workspaces WHERE id = %s", (workspace_id,))
                    if cur.fetchone()[0] == 0:
                        return {"success": False, "error": "Workspace không tồn tại"}
                    
                    # Tạo session
                    cur.execute("""
                        INSERT INTO chat_sessions (id, workspace_id, title, session_type)
                        VALUES (%s, %s, %s, %s)
                    """, (session_id, workspace_id, auto_title, session_type))
                    
                    conn.commit()
                    
                    return {
                        "success": True,
                        "session": {
                            "id": session_id,
                            "workspace_id": workspace_id,
                            "title": auto_title,
                            "session_type": session_type,
                            "message_count": 0,
                            "created_at": datetime.now()
                        }
                    }
                    
            except Exception as e:
                conn.rollback()
                return {"success": False, "error": f"Lỗi database: {str(e)}"}
            finally:
                self.db._safe_put_connection(conn)
                
        except Exception as e:
            return {"success": False, "error": f"Lỗi hệ thống: {str(e)}"}
    
    def get_sessions_by_workspace(self, workspace_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Lấy tất cả sessions trong workspace"""
        conn = self.db._safe_get_connection()
        if not conn:
            return []
        
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT cs.*, w.name as workspace_name, w.icon as workspace_icon
                    FROM chat_sessions cs
                    LEFT JOIN workspaces w ON cs.workspace_id = w.id
                    WHERE cs.workspace_id = %s 
                    ORDER BY cs.is_pinned DESC, cs.last_activity DESC
                    LIMIT %s
                """, (workspace_id, limit))
                
                sessions = []
                for row in cur.fetchall():
                    sessions.append(dict(row))
                
                return sessions
                
        except Exception as e:
            print(f"❌ Lỗi lấy chat sessions: {e}")
            return []
        finally:
            self.db._safe_put_connection(conn)
    
    def get_all_sessions(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Lấy tất cả sessions với thông tin workspace"""
        conn = self.db._safe_get_connection()
        if not conn:
            return []
        
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT cs.*, w.name as workspace_name, w.icon as workspace_icon, w.color as workspace_color
                    FROM chat_sessions cs
                    LEFT JOIN workspaces w ON cs.workspace_id = w.id
                    ORDER BY cs.is_pinned DESC, cs.last_activity DESC
                    LIMIT %s
                """, (limit,))
                
                sessions = []
                for row in cur.fetchall():
                    sessions.append(dict(row))
                
                return sessions
                
        except Exception as e:
            print(f"❌ Lỗi lấy all chat sessions: {e}")
            return []
        finally:
            self.db._safe_put_connection(conn)
    
    def get_session_by_id(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Lấy session theo ID"""
        conn = self.db._safe_get_connection()
        if not conn:
            return None
        
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT cs.*, w.name as workspace_name, w.icon as workspace_icon
                    FROM chat_sessions cs
                    LEFT JOIN workspaces w ON cs.workspace_id = w.id
                    WHERE cs.id = %s
                """, (session_id,))
                
                row = cur.fetchone()
                if row:
                    return dict(row)
                return None
                
        except Exception as e:
            print(f"❌ Lỗi lấy session {session_id}: {e}")
            return None
        finally:
            self.db._safe_put_connection(conn)
    
    def add_message_to_session(self, session_id: str, role: str, content: str, 
                              message_type: str = "text", sources: List[Dict] = None) -> Dict[str, Any]:
        """Thêm tin nhắn vào session"""
        try:
            conn = self.db._safe_get_connection()
            if not conn:
                return {"success": False, "error": "Không thể kết nối database"}
            
            try:
                with conn.cursor() as cur:
                    # Thêm message vào bảng messages
                    message_id = str(uuid.uuid4())
                    
                    # Lấy workspace từ session
                    cur.execute("SELECT workspace_id FROM chat_sessions WHERE id = %s", (session_id,))
                    session_row = cur.fetchone()
                    if not session_row:
                        return {"success": False, "error": "Session không tồn tại"}
                    
                    workspace_id = session_row[0] or 'main'
                    
                    # Insert message - chỉ sử dụng các cột có sẵn trong bảng messages
                    cur.execute("""
                        INSERT INTO messages (id, session_id, role, content, message_type, workspace, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                    """, (message_id, session_id, role, content, message_type, workspace_id))
                    
                    # Cập nhật session stats
                    cur.execute("""
                        UPDATE chat_sessions 
                        SET message_count = message_count + 1,
                            last_activity = CURRENT_TIMESTAMP,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """, (session_id,))
                    
                    # Auto-generate title cho session nếu đây là message đầu tiên từ user
                    cur.execute("""
                        SELECT message_count FROM chat_sessions WHERE id = %s
                    """, (session_id,))
                    msg_count = cur.fetchone()[0]
                    
                    if msg_count <= 2 and role == "user" and len(content) > 10:
                        # Tạo title từ nội dung tin nhắn đầu tiên
                        auto_title = self._generate_title_from_content(content)
                        cur.execute("""
                            UPDATE chat_sessions 
                            SET title = %s 
                            WHERE id = %s AND title LIKE 'Chat %'
                        """, (auto_title, session_id))
                    
                    conn.commit()
                    return {"success": True, "message_id": message_id}
                    
            except Exception as e:
                conn.rollback()
                return {"success": False, "error": f"Lỗi database: {str(e)}"}
            finally:
                self.db._safe_put_connection(conn)
                
        except Exception as e:
            return {"success": False, "error": f"Lỗi hệ thống: {str(e)}"}
    
    def get_session_messages(self, session_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Lấy tin nhắn trong session"""
        conn = self.db._safe_get_connection()
        if not conn:
            return []
        
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, role, content, message_type, created_at
                    FROM messages 
                    WHERE session_id = %s 
                    ORDER BY created_at ASC
                    LIMIT %s
                """, (session_id, limit))
                
                messages = []
                for row in cur.fetchall():
                    msg_dict = dict(row)
                    # Convert datetime to string for JSON serialization
                    if msg_dict.get('created_at'):
                        msg_dict['created_at'] = msg_dict['created_at'].isoformat()
                    messages.append(msg_dict)
                
                return messages
                
        except Exception as e:
            print(f"❌ Lỗi lấy messages cho session {session_id}: {e}")
            return []
        finally:
            self.db._safe_put_connection(conn)
    
    def update_session(self, session_id: str, **kwargs) -> Dict[str, Any]:
        """Cập nhật session"""
        try:
            conn = self.db._safe_get_connection()
            if not conn:
                return {"success": False, "error": "Không thể kết nối database"}
            
            # Tạo động SQL update
            update_fields = []
            values = []
            
            allowed_fields = ['title', 'summary', 'is_pinned', 'session_type', 'metadata']
            for field, value in kwargs.items():
                if field in allowed_fields:
                    if field == 'metadata' and isinstance(value, dict):
                        # Convert dict to JSON
                        update_fields.append(f"{field} = %s")
                        values.append(json.dumps(value))
                    else:
                        update_fields.append(f"{field} = %s")
                        values.append(value)
            
            if not update_fields:
                return {"success": False, "error": "Không có thông tin nào để cập nhật"}
            
            values.append(session_id)
            
            try:
                with conn.cursor() as cur:
                    sql = f"""
                        UPDATE chat_sessions 
                        SET {', '.join(update_fields)}, updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """
                    cur.execute(sql, values)
                    
                    if cur.rowcount == 0:
                        return {"success": False, "error": "Session không tồn tại"}
                    
                    conn.commit()
                    return {"success": True, "message": "Đã cập nhật session"}
                    
            except Exception as e:
                conn.rollback()
                return {"success": False, "error": f"Lỗi database: {str(e)}"}
            finally:
                self.db._safe_put_connection(conn)
                
        except Exception as e:
            return {"success": False, "error": f"Lỗi hệ thống: {str(e)}"}
    
    def delete_session(self, session_id: str) -> Dict[str, Any]:
        """Xóa session và tất cả messages"""
        try:
            conn = self.db._safe_get_connection()
            if not conn:
                return {"success": False, "error": "Không thể kết nối database"}
            
            try:
                with conn.cursor() as cur:
                    # Đếm messages sẽ bị xóa
                    cur.execute("SELECT COUNT(*) FROM messages WHERE session_id = %s", (session_id,))
                    message_count = cur.fetchone()[0]
                    
                    # Xóa messages trước
                    cur.execute("DELETE FROM messages WHERE session_id = %s", (session_id,))
                    
                    # Xóa session
                    cur.execute("DELETE FROM chat_sessions WHERE id = %s", (session_id,))
                    
                    if cur.rowcount == 0:
                        return {"success": False, "error": "Session không tồn tại"}
                    
                    conn.commit()
                    return {
                        "success": True, 
                        "message": f"Đã xóa session và {message_count} tin nhắn"
                    }
                    
            except Exception as e:
                conn.rollback()
                return {"success": False, "error": f"Lỗi database: {str(e)}"}
            finally:
                self.db._safe_put_connection(conn)
                
        except Exception as e:
            return {"success": False, "error": f"Lỗi hệ thống: {str(e)}"}
    
    def toggle_pin_session(self, session_id: str) -> Dict[str, Any]:
        """Toggle pin/unpin session"""
        try:
            conn = self.db._safe_get_connection()
            if not conn:
                return {"success": False, "error": "Không thể kết nối database"}
            
            try:
                with conn.cursor() as cur:
                    # Lấy trạng thái hiện tại
                    cur.execute("SELECT is_pinned FROM chat_sessions WHERE id = %s", (session_id,))
                    row = cur.fetchone()
                    
                    if not row:
                        return {"success": False, "error": "Session không tồn tại"}
                    
                    current_pinned = row[0]
                    new_pinned = not current_pinned
                    
                    # Cập nhật
                    cur.execute("""
                        UPDATE chat_sessions 
                        SET is_pinned = %s, updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """, (new_pinned, session_id))
                    
                    conn.commit()
                    
                    action = "Đã ghim" if new_pinned else "Đã bỏ ghim"
                    return {"success": True, "message": f"{action} session", "is_pinned": new_pinned}
                    
            except Exception as e:
                conn.rollback()
                return {"success": False, "error": f"Lỗi database: {str(e)}"}
            finally:
                self.db._safe_put_connection(conn)
                
        except Exception as e:
            return {"success": False, "error": f"Lỗi hệ thống: {str(e)}"}
    
    def generate_session_summary(self, session_id: str) -> Dict[str, Any]:
        """Tạo tóm tắt session bằng AI (placeholder)"""
        try:
            messages = self.get_session_messages(session_id)
            
            if not messages:
                return {"success": False, "error": "Session trống"}
            
            # Simple summary logic - sẽ được thay thế bằng AI trong tương lai
            user_messages = [msg for msg in messages if msg['role'] == 'user']
            
            if user_messages:
                # Lấy 3 tin nhắn đầu để tạo summary
                first_messages = user_messages[:3]
                summary_parts = []
                
                for msg in first_messages:
                    content = msg['content'][:100]  # Limit length
                    summary_parts.append(content)
                
                summary = " | ".join(summary_parts)
                if len(summary) > 200:
                    summary = summary[:200] + "..."
                
                # Cập nhật vào database
                result = self.update_session(session_id, summary=summary)
                
                if result['success']:
                    return {"success": True, "summary": summary}
                else:
                    return result
            else:
                return {"success": False, "error": "Không có tin nhắn người dùng để tạo summary"}
                
        except Exception as e:
            return {"success": False, "error": f"Lỗi tạo summary: {str(e)}"}
    
    def _generate_title_from_content(self, content: str) -> str:
        """Tạo title từ nội dung tin nhắn"""
        # Clean content
        content = content.strip()
        
        # Extract keywords for title
        keywords = []
        
        # Check for common Vietnamese question words
        question_words = ['tìm', 'tra', 'cứu', 'hỏi', 'gì', 'sao', 'thế nào', 'ở đâu', 'khi nào']
        for word in question_words:
            if word in content.lower():
                keywords.append(word)
                break
        
        # Extract potential technical terms
        technical_terms = ['tcvn', 'qcvn', 'tiêu chuẩn', 'quy chuẩn', 'bê tông', 'thép', 'xây dựng']
        for term in technical_terms:
            if term in content.lower():
                keywords.append(term.upper())
        
        # Create title
        if keywords:
            title = f"Chat về {' '.join(keywords[:2])}"
        else:
            # Fallback: use first few words
            words = content.split()[:5]
            title = ' '.join(words)
            if len(title) > 30:
                title = title[:30] + "..."
        
        return title
    
    def search_sessions(self, query: str, workspace_id: str = None) -> List[Dict[str, Any]]:
        """Tìm kiếm sessions theo query"""
        conn = self.db._safe_get_connection()
        if not conn:
            return []
        
        try:
            with conn.cursor() as cur:
                base_sql = """
                    SELECT DISTINCT cs.*, w.name as workspace_name, w.icon as workspace_icon
                    FROM chat_sessions cs
                    LEFT JOIN workspaces w ON cs.workspace_id = w.id
                    LEFT JOIN messages m ON cs.id = m.session_id
                    WHERE (
                        cs.title ILIKE %s OR 
                        cs.summary ILIKE %s OR 
                        m.content ILIKE %s
                    )
                """
                
                params = [f"%{query}%", f"%{query}%", f"%{query}%"]
                
                if workspace_id:
                    base_sql += " AND cs.workspace_id = %s"
                    params.append(workspace_id)
                
                base_sql += " ORDER BY cs.last_activity DESC LIMIT 20"
                
                cur.execute(base_sql, params)
                
                sessions = []
                for row in cur.fetchall():
                    sessions.append(dict(row))
                
                return sessions
                
        except Exception as e:
            print(f"❌ Lỗi tìm kiếm sessions: {e}")
            return []
        finally:
            self.db._safe_put_connection(conn)
    
    def get_session_stats(self, workspace_id: str = None) -> Dict[str, Any]:
        """Lấy thống kê session"""
        conn = self.db._safe_get_connection()
        if not conn:
            return {}
        
        try:
            with conn.cursor() as cur:
                # Base stats
                where_clause = ""
                params = []
                
                if workspace_id:
                    where_clause = "WHERE workspace_id = %s"
                    params.append(workspace_id)
                
                cur.execute(f"""
                    SELECT 
                        COUNT(*) as total_sessions,
                        COUNT(CASE WHEN is_pinned THEN 1 END) as pinned_sessions,
                        SUM(message_count) as total_messages,
                        AVG(message_count) as avg_messages_per_session
                    FROM chat_sessions
                    {where_clause}
                """, params)
                
                stats = dict(cur.fetchone())
                
                # Recent activity
                cur.execute(f"""
                    SELECT COUNT(*) as recent_sessions
                    FROM chat_sessions
                    WHERE last_activity >= NOW() - INTERVAL '7 days'
                    {('AND ' + where_clause) if where_clause else ''}
                """, params)
                
                recent_stats = dict(cur.fetchone())
                stats.update(recent_stats)
                
                return stats
                
        except Exception as e:
            print(f"❌ Lỗi lấy session stats: {e}")
            return {}
        finally:
            self.db._safe_put_connection(conn)