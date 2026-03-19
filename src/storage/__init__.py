"""
Storage - 存储层
"""
import aiosqlite
from typing import List, Dict, Any, Optional
from pathlib import Path


class Database:
    """数据库"""
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.db_path = self.config.get("path", "xuanling.db")
        self.conn = None
    
    async def init(self):
        """初始化数据库"""
        self.conn = await aiosqlite.connect(self.db_path)
        await self._create_tables()
    
    async def _create_tables(self):
        """创建表"""
        # 记忆表
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                type TEXT DEFAULT 'long_term',
                tags TEXT,
                importance INTEGER DEFAULT 1,
                created_at REAL
            )
        """)
        
        # 项目表
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                icon TEXT DEFAULT '📁',
                status TEXT DEFAULT 'active',
                progress INTEGER DEFAULT 0,
                created_at REAL,
                updated_at REAL
            )
        """)
        
        # 项目记忆表
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS project_memories (
                id TEXT PRIMARY KEY,
                project_id INTEGER,
                title TEXT NOT NULL,
                content TEXT,
                tags TEXT,
                importance INTEGER DEFAULT 1,
                created_at REAL,
                FOREIGN KEY (project_id) REFERENCES projects(id)
            )
        """)
        
        await self.conn.commit()
    
    async def save_memory(self, memory):
        """保存记忆"""
        import json
        await self.conn.execute(
            "INSERT OR REPLACE INTO memories (id, content, type, tags, importance, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (memory.id, memory.content, memory.memory_type, json.dumps(memory.tags), memory.importance, memory.created_at)
        )
        await self.conn.commit()
    
    async def get_all_memories(self) -> List[Dict]:
        """获取所有记忆"""
        import json
        cursor = await self.conn.execute("SELECT * FROM memories ORDER BY created_at DESC")
        rows = await cursor.fetchall()
        return [
            {
                "id": r[0],
                "content": r[1],
                "type": r[2],
                "tags": json.loads(r[3]) if r[3] else [],
                "importance": r[4],
                "created_at": r[5]
            }
            for r in rows
        ]
    
    async def search_memories(self, query: str) -> List[Dict]:
        """搜索记忆"""
        import json
        cursor = await self.conn.execute(
            "SELECT * FROM memories WHERE content LIKE ? ORDER BY importance DESC",
            (f"%{query}%",)
        )
        rows = await cursor.fetchall()
        return [
            {
                "id": r[0],
                "content": r[1],
                "type": r[2],
                "tags": json.loads(r[3]) if r[3] else [],
                "importance": r[4]
            }
            for r in rows
        ]
    
    async def delete_memory(self, memory_id: str):
        """删除记忆"""
        await self.conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        await self.conn.commit()
    
    async def create_project(self, name: str, description: str = "", icon: str = "📁") -> int:
        """创建项目"""
        import time
        cursor = await self.conn.execute(
            "INSERT INTO projects (name, description, icon, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (name, description, icon, time.time(), time.time())
        )
        await self.conn.commit()
        return cursor.lastrowid
    
    async def get_projects(self) -> List[Dict]:
        """获取项目列表"""
        cursor = await self.conn.execute("SELECT * FROM projects ORDER BY updated_at DESC")
        rows = await cursor.fetchall()
        return [
            {
                "id": r[0],
                "name": r[1],
                "description": r[2],
                "icon": r[3],
                "status": r[4],
                "progress": r[5]
            }
            for r in rows
        ]
    
    async def update_project(self, project_id: int, name: str = None, description: str = None, status: str = None, icon: str = None):
        """更新项目"""
        import time
        updates = []
        params = []
        if name is not None:
            updates.append("name = ?")
            params.append(name)
        if description is not None:
            updates.append("description = ?")
            params.append(description)
        if status is not None:
            updates.append("status = ?")
            params.append(status)
        if icon is not None:
            updates.append("icon = ?")
            params.append(icon)
        updates.append("updated_at = ?")
        params.append(time.time())
        params.append(project_id)
        
        await self.conn.execute(f"UPDATE projects SET {', '.join(updates)} WHERE id = ?", params)
        await self.conn.commit()
    
    async def delete_project(self, project_id: int):
        """删除项目"""
        await self.conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        await self.conn.commit()
    
    async def close(self):
        """关闭连接"""
        if self.conn:
            await self.conn.close()
