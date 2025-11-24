# database.py - Bản Sửa Lỗi (Final Fix 2 - Fix SQL Errors)
import os
import time
import hashlib
import uuid
from typing import List, Dict, Any, Optional

# Import thư viện
try:
    import psycopg2
    from psycopg2 import pool, extras
    import psycopg2.extras
except ImportError:
    print("❌ Thiếu psycopg2. Chạy: pip install psycopg2-binary")

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    print("❌ Thiếu sentence-transformers")

try:
    from pymilvus import connections, Collection, FieldSchema, CollectionSchema, DataType, utility
except ImportError:
    print("❌ Thiếu pymilvus")

try:
    from flashrank import Ranker, RerankRequest
    HAS_RERANKER = True
except ImportError:
    HAS_RERANKER = False

class DatabaseManager:
    def __init__(self):
        print("🔄 Khởi tạo Database Manager...")
        
        self.postgres_dsn = "postgresql://user:password@localhost:5432/ai_chatbot_db"
        self.postgres_pool = None
        
        self.milvus_host = "localhost"
        self.milvus_port = "19530"
        self.collection_name = "document_embeddings_vn_v1" 
        self.milvus_collection = None
        
        self.embedder = None
        self.reranker = None
        self.embedding_dimension = 768 
        
        self._init_models()
        self.connect_postgres()
        self.connect_milvus()
    
    def _init_models(self):
        try:
            print("🧠 Đang tải Model Embedding...")
            self.embedder = SentenceTransformer('keepitreal/vietnamese-sbert')
            if HAS_RERANKER:
                self.reranker = Ranker(model_name="ms-marco-MiniLM-L-12-v2", cache_dir="opt")
            return True
        except Exception as e:
            print(f"❌ Lỗi tải model: {e}")
            return False
            
    def _safe_get_connection(self):
        if not self.postgres_pool: return None
        try:
            return self.postgres_pool.getconn()
        except: return None

    def _safe_put_connection(self, conn):
        if self.postgres_pool and conn:
            try:
                self.postgres_pool.putconn(conn)
            except: pass

    def connect_postgres(self):
        try:
            self.postgres_pool = psycopg2.pool.ThreadedConnectionPool(
                1, 5, dsn=self.postgres_dsn, cursor_factory=psycopg2.extras.RealDictCursor
            )
            conn = self._safe_get_connection()
            if conn:
                with conn.cursor() as cur:
                    # 1. Tạo bảng documents
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS documents (
                            id VARCHAR(100) PRIMARY KEY,
                            file_name VARCHAR(255),
                            project_name VARCHAR(100),
                            workspace VARCHAR(100) DEFAULT 'main',
                            status VARCHAR(50),
                            file_size BIGINT,
                            chunks_created INTEGER DEFAULT 0,
                            upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """)
                    
                    # 2. Tạo bảng chunks
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS chunks (
                            chunk_id VARCHAR(100) PRIMARY KEY,
                            document_id VARCHAR(100),
                            content TEXT,
                            chunk_index INTEGER,
                            workspace VARCHAR(100) DEFAULT 'main',
                            project_name VARCHAR(100)
                        )
                    """)
                    
                    # 3. Tạo bảng workspaces (MỚI)
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS workspaces (
                            id VARCHAR(100) PRIMARY KEY,
                            name VARCHAR(200),
                            description TEXT,
                            color VARCHAR(20),
                            icon VARCHAR(20),
                            access_level VARCHAR(20),
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """)
                    
                    # 4. Tạo bảng chat_sessions (MỚI)
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
                            metadata JSONB DEFAULT '{}'
                        )
                    """)

                    # 5. Tạo bảng messages (MỚI - Thay thế bảng cũ nếu cần)
                    # Lưu ý: Nếu bảng messages cũ đã có nhưng thiếu cột, lệnh này sẽ không chạy lại CREATE TABLE
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS messages (
                            id VARCHAR(100) PRIMARY KEY,
                            session_id VARCHAR(100),
                            role VARCHAR(50),
                            content TEXT,
                            message_type VARCHAR(50) DEFAULT 'text',
                            workspace VARCHAR(100) DEFAULT 'main',
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    """)

                    # 6. Thêm cột session_id vào messages nếu chưa có (Migration an toàn)
                    try:
                        cur.execute("""
                            DO $$ 
                            BEGIN
                                BEGIN
                                    ALTER TABLE messages ADD COLUMN session_id VARCHAR(100);
                                EXCEPTION
                                    WHEN duplicate_column THEN NULL;
                                END;
                            END $$;
                        """)
                    except:
                        conn.rollback() # Rollback nếu lỗi để tiếp tục

                    # 7. Thêm workspace mặc định
                    cur.execute("INSERT INTO workspaces (id, name, icon) VALUES ('main', 'Chính', '📁') ON CONFLICT (id) DO NOTHING")
                    
                    conn.commit()
                self._safe_put_connection(conn)
                return True
        except Exception as e:
            print(f"❌ Lỗi PostgreSQL Init: {e}")
            return False

    def connect_milvus(self):
        try:
            connections.connect("default", host=self.milvus_host, port=self.milvus_port)
            if not utility.has_collection(self.collection_name):
                fields = [
                    FieldSchema(name="id", dtype=DataType.VARCHAR, max_length=100, is_primary=True),
                    FieldSchema(name="document_id", dtype=DataType.VARCHAR, max_length=100),
                    FieldSchema(name="chunk_index", dtype=DataType.INT64),
                    FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.embedding_dimension),
                    FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=6000)
                ]
                schema = CollectionSchema(fields, "Vietnamese Embeddings")
                self.milvus_collection = Collection(self.collection_name, schema)
                index_params = {"metric_type": "COSINE", "index_type": "IVF_FLAT", "params": {"nlist": 128}}
                self.milvus_collection.create_index("embedding", index_params)
            else:
                self.milvus_collection = Collection(self.collection_name)
            self.milvus_collection.load()
            return True
        except Exception as e:
            print(f"❌ Lỗi Milvus: {e}")
            return False

    def save_document_record(self, doc_data):
        conn = self._safe_get_connection()
        if not conn: return False
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO documents (id, file_name, project_name, workspace, status, file_size)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (id) DO NOTHING
                """, (doc_data['id'], doc_data['file_name'], doc_data['project_name'], 
                      doc_data['workspace'], doc_data['status'], doc_data['file_size']))
                conn.commit()
                return True
        except Exception as e:
            print(f"Lỗi lưu doc: {e}")
            return False
        finally:
            self._safe_put_connection(conn)

    def save_chunk_record(self, chunk_data):
        conn = self._safe_get_connection()
        if not conn: return False
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO chunks (chunk_id, document_id, content, chunk_index, workspace, project_name)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (chunk_data['chunk_id'], chunk_data['document_id'], chunk_data['content'], 
                      chunk_data['chunk_index'], chunk_data['workspace'], chunk_data['project_name']))
                conn.commit()
        finally:
            self._safe_put_connection(conn)

        if self.milvus_collection and self.embedder:
            try:
                vector = self.embedder.encode([chunk_data['content']])[0]
                entity = [
                    [chunk_data['chunk_id']], [chunk_data['document_id']],
                    [chunk_data['chunk_index']], [vector.tolist()],
                    [chunk_data['content'][:6000]]
                ]
                self.milvus_collection.insert(entity)
                return True
            except: return False
        return False

    def update_document_status(self, doc_id, status, msg=""):
        conn = self._safe_get_connection()
        if not conn: return
        try:
            with conn.cursor() as cur:
                cur.execute("UPDATE documents SET status = %s WHERE id = %s", (status, doc_id))
                conn.commit()
        finally:
            self._safe_put_connection(conn)

    def get_documents_from_db(self, workspace, limit=50):
        conn = self._safe_get_connection()
        if not conn: return []
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM documents WHERE workspace = %s ORDER BY upload_date DESC LIMIT %s", (workspace, limit))
                return cur.fetchall()
        finally:
            self._safe_put_connection(conn)
            
    def get_document_count(self, workspace):
        conn = self._safe_get_connection()
        if not conn: return 0
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM documents WHERE workspace = %s", (workspace,))
                return cur.fetchone()['count']
        except: return 0
        finally: self._safe_put_connection(conn)

    def delete_document(self, doc_id):
        conn = self._safe_get_connection()
        if not conn: return False
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM chunks WHERE document_id = %s", (doc_id,))
                cur.execute("DELETE FROM documents WHERE id = %s", (doc_id,))
                conn.commit()
            if self.milvus_collection:
                self.milvus_collection.delete(f'document_id == "{doc_id}"')
                self.milvus_collection.flush()
            return True
        except: return False
        finally: self._safe_put_connection(conn)

    def rag_search(self, query, workspace, top_k=5):
        candidates = {}
        print(f"🔍 Đang tìm kiếm: '{query}'...")

        if self.milvus_collection and self.embedder:
            try:
                query_vector = self.embedder.encode([query])
                res = self.milvus_collection.search(
                    data=query_vector.tolist(),
                    anns_field="embedding",
                    param={"metric_type": "COSINE", "params": {"nprobe": 10}},
                    limit=top_k * 2,
                    output_fields=["content", "document_id", "chunk_index"]
                )
                if res:
                    for hits in res:
                        for hit in hits:
                            candidates[hit.id] = {
                                "id": hit.id,
                                "content": hit.entity.get('content'),
                                "file_name": self._get_filename(hit.entity.get('document_id')),
                                "score": hit.score,
                                "source": "Vector"
                            }
            except Exception as e:
                print(f"⚠️ Lỗi Vector search: {e}")

        conn = self._safe_get_connection()
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT c.chunk_id, c.content, d.file_name 
                        FROM chunks c
                        JOIN documents d ON c.document_id = d.id
                        WHERE c.workspace = %s AND c.content ILIKE %s
                        LIMIT %s
                    """, (workspace, f"%{query}%", top_k * 2))
                    rows = cur.fetchall()
                    for row in rows:
                        if row['chunk_id'] not in candidates:
                            candidates[row['chunk_id']] = {
                                "id": row['chunk_id'],
                                "content": row['content'],
                                "file_name": row['file_name'],
                                "score": 0.5,
                                "source": "Keyword"
                            }
            except Exception as e:
                print(f"⚠️ Lỗi Keyword search: {e}")
            finally:
                self._safe_put_connection(conn)

        candidate_list = list(candidates.values())
        if not candidate_list: return [], []

        if HAS_RERANKER and self.reranker:
            try:
                passages = [{"id": item["id"], "text": item["content"], "meta": item} for item in candidate_list]
                rerank_request = RerankRequest(query=query, passages=passages)
                results = self.reranker.rank(rerank_request)
                final_results = []
                for res in results[:top_k]:
                    meta = res['meta']
                    meta['similarity_score'] = res['score']
                    final_results.append(meta)
                return final_results, []
            except Exception as e:
                print(f"⚠️ Lỗi Re-ranking: {e}")
        
        return candidate_list[:top_k], []

    def _get_filename(self, doc_id):
        conn = self._safe_get_connection()
        if not conn: return "Unknown"
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT file_name FROM documents WHERE id = %s", (doc_id,))
                res = cur.fetchone()
                return res['file_name'] if res else "Unknown"
        finally:
            self._safe_put_connection(conn)

    def health_check(self):
        conn = self._safe_get_connection()
        pg_ok = conn is not None
        if conn: self._safe_put_connection(conn)
        return {"postgres": pg_ok, "milvus": self.milvus_collection is not None}

db_manager = DatabaseManager()