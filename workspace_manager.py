# workspace_manager.py - Sửa lỗi SQL query (c.id -> c.chunk_id)
import os
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional

class WorkspaceManager:
    """Quản lý workspace system với database integration"""
    
    def __init__(self, db_manager):
        self.db = db_manager
        self._create_workspace_table()
        self._initialize_default_workspaces()
    
    def _create_workspace_table(self):
        """Tạo bảng workspaces và cập nhật schema"""
        conn = self.db._safe_get_connection()
        if not conn:
            return False
        
        try:
            with conn.cursor() as cur:
                # Tạo bảng workspaces (Đã có trong database.py, nhưng check lại cho chắc)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS workspaces (
                        id VARCHAR(100) PRIMARY KEY,
                        name VARCHAR(200) NOT NULL,
                        description TEXT,
                        color VARCHAR(20) DEFAULT '#2196F3',
                        icon VARCHAR(20) DEFAULT '📁',
                        access_level VARCHAR(20) DEFAULT 'private',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.commit()
                return True
        except Exception as e:
            print(f"❌ Lỗi tạo workspace tables: {e}")
            conn.rollback()
            return False
        finally:
            self.db._safe_put_connection(conn)
    
    def _initialize_default_workspaces(self):
        """Tạo workspace mặc định"""
        self.create_workspace('Chính', 'Workspace mặc định', icon='📁')

    def create_workspace(self, name: str, description: str = "", 
                        color: str = "#2196F3", icon: str = "📁", 
                        access_level: str = "private") -> Dict[str, Any]:
        workspace_id = f"ws_{str(uuid.uuid4())[:8]}"
        if name == 'Chính': workspace_id = 'main'
        
        conn = self.db._safe_get_connection()
        if not conn: return {"success": False, "error": "Lỗi kết nối DB"}
        
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO workspaces (id, name, description, color, icon, access_level)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING
                """, (workspace_id, name, description, color, icon, access_level))
                conn.commit()
                return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            self.db._safe_put_connection(conn)
    
    def get_all_workspaces(self) -> List[Dict[str, Any]]:
        """Lấy tất cả workspace với thống kê (FIXED SQL)"""
        conn = self.db._safe_get_connection()
        if not conn: return []
        
        try:
            with conn.cursor() as cur:
                # SỬA LỖI: COUNT(c.id) -> COUNT(c.chunk_id)
                cur.execute("""
                    SELECT 
                        w.*,
                        COALESCE(doc_stats.document_count, 0) as document_count,
                        COALESCE(chunk_stats.chunk_count, 0) as chunk_count
                    FROM workspaces w
                    LEFT JOIN (
                        SELECT workspace, COUNT(*) as document_count 
                        FROM documents 
                        GROUP BY workspace
                    ) doc_stats ON w.id = doc_stats.workspace
                    LEFT JOIN (
                        SELECT d.workspace, COUNT(c.chunk_id) as chunk_count
                        FROM documents d
                        LEFT JOIN chunks c ON d.id = c.document_id
                        GROUP BY d.workspace
                    ) chunk_stats ON w.id = chunk_stats.workspace
                    ORDER BY 
                        CASE WHEN w.id = 'main' THEN 0 ELSE 1 END,
                        w.created_at ASC
                """)
                
                workspaces = []
                for row in cur.fetchall():
                    ws = dict(row)
                    ws['document_count'] = ws.get('document_count', 0)
                    ws['chunk_count'] = ws.get('chunk_count', 0)
                    workspaces.append(ws)
                return workspaces
        except Exception as e:
            print(f"❌ Lỗi lấy workspaces: {e}")
            return []
        finally:
            self.db._safe_put_connection(conn)
    
    def get_workspace_by_id(self, workspace_id: str) -> Optional[Dict[str, Any]]:
        conn = self.db._safe_get_connection()
        if not conn: return None
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM workspaces WHERE id = %s", (workspace_id,))
                row = cur.fetchone()
                return dict(row) if row else None
        finally:
            self.db._safe_put_connection(conn)

    def migrate_existing_documents_to_main(self):
        conn = self.db._safe_get_connection()
        if not conn: return
        try:
            with conn.cursor() as cur:
                cur.execute("UPDATE documents SET workspace = 'main' WHERE workspace IS NULL")
                conn.commit()
        finally:
            self.db._safe_put_connection(conn)
            
    def assign_document_to_workspace(self, doc_id, ws_id):
        conn = self.db._safe_get_connection()
        if not conn: return
        try:
            with conn.cursor() as cur:
                cur.execute("UPDATE documents SET workspace = %s WHERE id = %s", (ws_id, doc_id))
                conn.commit()
        finally:
            self.db._safe_put_connection(conn)