"""
玄灵AI 项目管理模块
支持：项目管理、任务下达、文档上传、智能解析
"""
import os
import json
import uuid
import logging
import asyncio
import shutil
import re
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger("玄灵AI.ProjectManager")

# ============== 配置 ==============

PROJECTS_DIR = Path(__file__).parent.parent / "projects"
UPLOADS_DIR = Path(__file__).parent.parent / "uploads"
PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

# ============== 枚举 ==============

class ProjectStatus(Enum):
    """项目状态"""
    DRAFT = "draft"           # 草稿
    PLANNING = "planning"     # 规划中
    IN_PROGRESS = "in_progress"  # 进行中
    ON_HOLD = "on_hold"       # 暂停
    COMPLETED = "completed"   # 已完成
    CANCELLED = "cancelled"   # 已取消

class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"       # 待处理
    ASSIGNED = "assigned"     # 已分配
    IN_PROGRESS = "in_progress"  # 进行中
    REVIEW = "review"         # 审核中
    COMPLETED = "completed"   # 已完成
    FAILED = "failed"         # 失败

class TaskPriority(Enum):
    """任务优先级"""
    LOW = 1
    NORMAL = 5
    HIGH = 10
    CRITICAL = 20
    URGENT = 30

class DocumentType(Enum):
    """文档类型"""
    REQUIREMENT = "requirement"   # 需求文档
    DESIGN = "design"             # 设计文档
    TECHNICAL = "technical"       # 技术文档
    MANUAL = "manual"             # 手册
    REFERENCE = "reference"       # 参考资料
    OTHER = "other"               # 其他


# ============== 数据模型 ==============

@dataclass
class ProjectTask:
    """项目任务"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    title: str = ""
    description: str = ""
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.NORMAL
    assignee: Optional[str] = None  # 分配给的代理/用户
    project_id: str = ""
    parent_task_id: Optional[str] = None
    sub_tasks: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    due_date: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: float = 0.0  # 0.0 - 1.0
    estimated_hours: Optional[float] = None
    actual_hours: Optional[float] = None
    source: str = "manual"  # manual / document / ai_parsed
    source_document_id: Optional[str] = None
    result: Optional[Dict] = None
    notes: List[Dict] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "priority": self.priority.value,
            "assignee": self.assignee,
            "project_id": self.project_id,
            "parent_task_id": self.parent_task_id,
            "sub_tasks": self.sub_tasks,
            "dependencies": self.dependencies,
            "tags": self.tags,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "progress": self.progress,
            "estimated_hours": self.estimated_hours,
            "source": self.source,
            "source_document_id": self.source_document_id
        }


@dataclass
class ProjectDocument:
    """项目文档"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    filename: str = ""
    original_name: str = ""
    file_path: str = ""
    file_size: int = 0
    file_type: str = ""  # mime type
    document_type: DocumentType = DocumentType.OTHER
    project_id: str = ""
    description: str = ""
    tags: List[str] = field(default_factory=list)
    uploaded_by: Optional[str] = None
    uploaded_at: datetime = field(default_factory=datetime.now)
    parsed: bool = False
    parsed_tasks: List[str] = field(default_factory=list)  # 解析出的任务ID
    content_preview: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "filename": self.filename,
            "original_name": self.original_name,
            "file_path": self.file_path,
            "file_size": self.file_size,
            "file_type": self.file_type,
            "document_type": self.document_type.value,
            "project_id": self.project_id,
            "description": self.description,
            "tags": self.tags,
            "uploaded_at": self.uploaded_at.isoformat(),
            "parsed": self.parsed,
            "parsed_tasks": self.parsed_tasks,
            "content_preview": self.content_preview[:500] if self.content_preview else ""
        }


@dataclass
class Project:
    """项目"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    description: str = ""
    status: ProjectStatus = ProjectStatus.DRAFT
    owner: Optional[str] = None
    team: List[str] = field(default_factory=list)
    tasks: List[str] = field(default_factory=list)  # 任务ID列表
    documents: List[str] = field(default_factory=list)  # 文档ID列表
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    deadline: Optional[datetime] = None
    progress: float = 0.0
    icon: str = "📁"
    color: str = "#667eea"
    settings: Dict[str, Any] = field(default_factory=dict)
    stats: Dict[str, int] = field(default_factory=lambda: {
        "total_tasks": 0,
        "completed_tasks": 0,
        "total_documents": 0,
        "total_hours": 0
    })
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "owner": self.owner,
            "team": self.team,
            "tasks": self.tasks,
            "documents": self.documents,
            "tags": self.tags,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "progress": self.progress,
            "icon": self.icon,
            "color": self.color,
            "stats": self.stats
        }


# ============== 任务解析器 ==============

class TaskParser:
    """任务解析器 - 从文字/文档中提取任务"""
    
    def __init__(self, ai_engine=None):
        self.ai_engine = ai_engine
        
        # 任务关键词模式
        self.task_patterns = [
            r'(?:需要|必须|要|应该)[做完成开发实现写设计测试]{1,3}[：:]?\s*(.+)',
            r'(?:任务|TODO|FIXME)[：:]\s*(.+)',
            r'[-•]\s*(.+)',  # 列表项
            r'\d+[\.、]\s*(.+)',  # 编号列表
            r'(?:第一步|第二步|第三步|首先|然后|最后)[，,：:]?\s*(.+)',
        ]
        
        # 优先级关键词
        self.priority_keywords = {
            TaskPriority.URGENT: ['紧急', '立即', '马上', 'ASAP', 'urgent'],
            TaskPriority.CRITICAL: ['关键', '重要', '核心', 'critical', 'important'],
            TaskPriority.HIGH: ['优先', '尽快', 'high'],
            TaskPriority.LOW: ['低优先', '不急', '后续', 'low'],
        }
    
    async def parse_text(self, text: str, project_id: str = None) -> List[ProjectTask]:
        """从文字中解析任务"""
        tasks = []
        lines = text.split('\n')
        
        current_task = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 尝试匹配任务模式
            matched = False
            for pattern in self.task_patterns:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    task_title = match.group(1).strip()
                    if len(task_title) > 3:  # 过滤太短的内容
                        task = self._create_task(task_title, line, project_id)
                        tasks.append(task)
                        matched = True
                        break
            
            # 如果没匹配到模式，但行看起来像任务描述
            if not matched and len(line) > 10 and len(line) < 200:
                # 检查是否包含动词
                verbs = ['开发', '实现', '设计', '测试', '编写', '创建', '修改', '优化', '修复', '添加', '删除', '更新']
                if any(v in line for v in verbs):
                    task = self._create_task(line, line, project_id)
                    tasks.append(task)
        
        return tasks
    
    def _create_task(self, title: str, full_text: str, project_id: str) -> ProjectTask:
        """创建任务"""
        # 检测优先级
        priority = TaskPriority.NORMAL
        for p, keywords in self.priority_keywords.items():
            if any(kw in full_text for kw in keywords):
                priority = p
                break
        
        return ProjectTask(
            title=title[:100],  # 限制标题长度
            description=full_text,
            priority=priority,
            project_id=project_id,
            source="text"
        )
    
    async def parse_document(self, document: ProjectDocument, project_id: str = None) -> List[ProjectTask]:
        """从文档中解析任务"""
        tasks = []
        
        try:
            file_path = Path(document.file_path)
            
            if not file_path.exists():
                logger.error(f"文档不存在: {file_path}")
                return tasks
            
            # 读取文档内容
            content = ""
            if file_path.suffix in ['.txt', '.md', '.json', '.yaml', '.yml', '.py', '.js', '.ts']:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            elif file_path.suffix in ['.docx', '.doc']:
                # TODO: 使用 python-docx 解析
                content = f"[Word文档: {document.original_name}]"
            elif file_path.suffix == '.pdf':
                # TODO: 使用 PyPDF2 解析
                content = f"[PDF文档: {document.original_name}]"
            else:
                content = f"[文档: {document.original_name}]"
            
            # 解析内容
            if content:
                tasks = await self.parse_text(content, project_id)
                
                # 标记任务来源
                for task in tasks:
                    task.source = "document"
                    task.source_document_id = document.id
                
                logger.info(f"从文档 {document.original_name} 解析出 {len(tasks)} 个任务")
        
        except Exception as e:
            logger.error(f"解析文档失败: {e}", exc_info=True)
        
        return tasks


# ============== 项目管理器 ==============

class ProjectManager:
    """项目管理器"""
    
    def __init__(self, data_dir: Path = None):
        self.data_dir = data_dir or PROJECTS_DIR
        self.data_file = self.data_dir / "projects_data.json"
        
        self._projects: Dict[str, Project] = {}
        self._tasks: Dict[str, ProjectTask] = {}
        self._documents: Dict[str, ProjectDocument] = {}
        
        self._parser = TaskParser()
        
        self._load()
    
    def _load(self):
        """加载数据"""
        if self.data_file.exists():
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # 加载项目
                for p in data.get("projects", []):
                    project = Project(
                        id=p.get("id"),
                        name=p.get("name", ""),
                        description=p.get("description", ""),
                        status=ProjectStatus(p.get("status", "draft")),
                        owner=p.get("owner"),
                        team=p.get("team", []),
                        tasks=p.get("tasks", []),
                        documents=p.get("documents", []),
                        tags=p.get("tags", []),
                        icon=p.get("icon", "📁"),
                        color=p.get("color", "#667eea"),
                        progress=p.get("progress", 0.0),
                    )
                    self._projects[project.id] = project
                
                # 加载任务
                for t in data.get("tasks", []):
                    task = ProjectTask(
                        id=t.get("id"),
                        title=t.get("title", ""),
                        description=t.get("description", ""),
                        status=TaskStatus(t.get("status", "pending")),
                        priority=TaskPriority(t.get("priority", 5)),
                        assignee=t.get("assignee"),
                        project_id=t.get("project_id", ""),
                        tags=t.get("tags", []),
                        progress=t.get("progress", 0.0),
                        source=t.get("source", "manual"),
                    )
                    self._tasks[task.id] = task
                
                # 加载文档
                for d in data.get("documents", []):
                    doc = ProjectDocument(
                        id=d.get("id"),
                        filename=d.get("filename", ""),
                        original_name=d.get("original_name", ""),
                        file_path=d.get("file_path", ""),
                        file_size=d.get("file_size", 0),
                        file_type=d.get("file_type", ""),
                        document_type=DocumentType(d.get("document_type", "other")),
                        project_id=d.get("project_id", ""),
                        parsed=d.get("parsed", False),
                    )
                    self._documents[doc.id] = doc
                
                logger.info(f"📂 加载 {len(self._projects)} 个项目, {len(self._tasks)} 个任务, {len(self._documents)} 个文档")
                
            except Exception as e:
                logger.error(f"加载数据失败: {e}")
    
    def _save(self):
        """保存数据"""
        data = {
            "projects": [p.to_dict() for p in self._projects.values()],
            "tasks": [t.to_dict() for t in self._tasks.values()],
            "documents": [d.to_dict() for d in self._documents.values()],
            "updated_at": datetime.now().isoformat()
        }
        
        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    # ============== 项目操作 ==============
    
    def create_project(
        self,
        name: str,
        description: str = "",
        owner: str = None,
        tags: List[str] = None,
        icon: str = "📁",
        color: str = "#667eea"
    ) -> Project:
        """创建项目"""
        project = Project(
            name=name,
            description=description,
            owner=owner,
            tags=tags or [],
            icon=icon,
            color=color
        )
        
        # 创建项目文件夹
        project_dir = PROJECTS_DIR / project.id
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "documents").mkdir(exist_ok=True)
        (project_dir / "output").mkdir(exist_ok=True)
        
        self._projects[project.id] = project
        self._save()
        
        logger.info(f"📁 创建项目: {name} (ID: {project.id})")
        return project
    
    def get_project(self, project_id: str) -> Optional[Project]:
        """获取项目"""
        return self._projects.get(project_id)
    
    def update_project(self, project_id: str, **kwargs) -> Optional[Project]:
        """更新项目"""
        project = self._projects.get(project_id)
        if not project:
            return None
        
        for key, value in kwargs.items():
            if hasattr(project, key):
                if key == "status" and isinstance(value, str):
                    value = ProjectStatus(value)
                setattr(project, key, value)
        
        project.updated_at = datetime.now()
        self._save()
        return project
    
    def delete_project(self, project_id: str) -> bool:
        """删除项目 (带事务保护)"""
        if project_id not in self._projects:
            return False
        
        project = self._projects[project_id]
        project_name = project.name
        
        # 备份当前数据状态
        backup_data = {
            "project": project.to_dict(),
            "tasks": {tid: self._tasks.get(tid).to_dict() if self._tasks.get(tid) else None 
                      for tid in project.tasks},
            "documents": {did: self._documents.get(did).to_dict() if self._documents.get(did) else None 
                         for did in project.documents}
        }
        
        try:
            # 1. 删除关联的任务
            for task_id in project.tasks:
                self._tasks.pop(task_id, None)
            
            # 2. 删除关联的文档文件
            deleted_docs = []
            for doc_id in project.documents:
                doc = self._documents.pop(doc_id, None)
                if doc:
                    doc_path = Path(doc.file_path)
                    if doc_path.exists():
                        try:
                            doc_path.unlink()
                            deleted_docs.append(doc_id)
                        except Exception as e:
                            logger.warning(f"删除文档文件失败: {doc_path} - {e}")
            
            # 3. 删除项目文件夹
            project_dir = PROJECTS_DIR / project_id
            if project_dir.exists():
                try:
                    shutil.rmtree(project_dir)
                except Exception as e:
                    logger.warning(f"删除项目文件夹失败: {project_dir} - {e}")
            
            # 4. 从项目列表中移除
            del self._projects[project_id]
            
            # 5. 保存数据
            self._save()
            
            logger.info(f"🗑️ 删除项目: {project_name} (任务: {len(project.tasks)}, 文档: {len(deleted_docs)})")
            return True
            
        except Exception as e:
            logger.error(f"删除项目失败，正在回滚: {e}")
            
            # 回滚操作
            try:
                # 恢复项目
                self._projects[project_id] = project
                
                # 恢复任务
                for task_id, task_data in backup_data["tasks"].items():
                    if task_data:
                        # 重新创建任务对象
                        self._tasks[task_id] = ProjectTask(
                            id=task_data.get("id"),
                            title=task_data.get("title", ""),
                            description=task_data.get("description", ""),
                            project_id=project_id
                        )
                
                # 恢复文档记录
                for doc_id, doc_data in backup_data["documents"].items():
                    if doc_data:
                        self._documents[doc_id] = ProjectDocument(
                            id=doc_data.get("id"),
                            filename=doc_data.get("filename", ""),
                            original_name=doc_data.get("original_name", ""),
                            file_path=doc_data.get("file_path", ""),
                            project_id=project_id
                        )
                
                self._save()
                logger.info(f"项目删除已回滚: {project_name}")
            except Exception as rollback_err:
                logger.error(f"回滚失败: {rollback_err}")
            
            return False
    
    def list_projects(self, status: ProjectStatus = None, owner: str = None) -> List[Project]:
        """列出项目"""
        projects = list(self._projects.values())
        
        if status:
            projects = [p for p in projects if p.status == status]
        if owner:
            projects = [p for p in projects if p.owner == owner]
        
        return projects
    
    # ============== 任务操作 ==============
    
    async def create_task(
        self,
        project_id: str,
        title: str,
        description: str = "",
        priority: TaskPriority = TaskPriority.NORMAL,
        assignee: str = None,
        tags: List[str] = None,
        due_date: datetime = None
    ) -> Optional[ProjectTask]:
        """创建任务"""
        project = self._projects.get(project_id)
        if not project:
            return None
        
        task = ProjectTask(
            title=title,
            description=description,
            priority=priority,
            assignee=assignee,
            project_id=project_id,
            tags=tags or [],
            due_date=due_date
        )
        
        self._tasks[task.id] = task
        project.tasks.append(task.id)
        project.stats["total_tasks"] += 1
        project.updated_at = datetime.now()
        
        self._save()
        
        logger.info(f"✅ 创建任务: {title} (项目: {project.name})")
        return task
    
    async def create_tasks_from_text(
        self,
        project_id: str,
        text: str
    ) -> List[ProjectTask]:
        """从文字创建任务"""
        project = self._projects.get(project_id)
        if not project:
            return []
        
        # 解析文字
        parsed_tasks = await self._parser.parse_text(text, project_id)
        
        # 保存任务
        for task in parsed_tasks:
            self._tasks[task.id] = task
            project.tasks.append(task.id)
        
        project.stats["total_tasks"] += len(parsed_tasks)
        project.updated_at = datetime.now()
        self._save()
        
        logger.info(f"📝 从文字创建 {len(parsed_tasks)} 个任务 (项目: {project.name})")
        return parsed_tasks
    
    def get_task(self, task_id: str) -> Optional[ProjectTask]:
        """获取任务"""
        return self._tasks.get(task_id)
    
    def update_task(self, task_id: str, **kwargs) -> Optional[ProjectTask]:
        """更新任务"""
        task = self._tasks.get(task_id)
        if not task:
            return None
        
        for key, value in kwargs.items():
            if hasattr(task, key):
                if key == "status" and isinstance(value, str):
                    value = TaskStatus(value)
                    # 更新时间戳
                    if value == TaskStatus.IN_PROGRESS and not task.started_at:
                        task.started_at = datetime.now()
                    elif value == TaskStatus.COMPLETED:
                        task.completed_at = datetime.now()
                        task.progress = 1.0
                elif key == "priority" and isinstance(value, (int, str)):
                    value = TaskPriority(int(value) if isinstance(value, int) else value)
                setattr(task, key, value)
        
        task.updated_at = datetime.now()
        
        # 更新项目进度
        self._update_project_progress(task.project_id)
        self._save()
        
        return task
    
    def delete_task(self, task_id: str) -> bool:
        """删除任务"""
        if task_id not in self._tasks:
            return False
        
        task = self._tasks[task_id]
        project = self._projects.get(task.project_id)
        
        if project and task_id in project.tasks:
            project.tasks.remove(task_id)
            project.stats["total_tasks"] -= 1
        
        del self._tasks[task_id]
        self._save()
        
        return True
    
    def list_tasks(
        self,
        project_id: str = None,
        status: TaskStatus = None,
        assignee: str = None
    ) -> List[ProjectTask]:
        """列出任务"""
        tasks = list(self._tasks.values())
        
        if project_id:
            tasks = [t for t in tasks if t.project_id == project_id]
        if status:
            tasks = [t for t in tasks if t.status == status]
        if assignee:
            tasks = [t for t in tasks if t.assignee == assignee]
        
        return tasks
    
    def _update_project_progress(self, project_id: str):
        """更新项目进度"""
        project = self._projects.get(project_id)
        if not project or not project.tasks:
            return
        
        tasks = [self._tasks.get(tid) for tid in project.tasks if tid in self._tasks]
        if tasks:
            completed = len([t for t in tasks if t.status == TaskStatus.COMPLETED])
            project.progress = completed / len(tasks)
            project.stats["completed_tasks"] = completed
    
    # ============== 文档操作 ==============
    
    async def upload_document(
        self,
        project_id: str,
        file_content: bytes,
        filename: str,
        document_type: DocumentType = DocumentType.OTHER,
        description: str = "",
        uploaded_by: str = None
    ) -> Optional[ProjectDocument]:
        """上传文档"""
        project = self._projects.get(project_id)
        if not project:
            return None
        
        # 生成唯一文件名
        file_ext = Path(filename).suffix
        unique_filename = f"{uuid.uuid4().hex}{file_ext}"
        
        # 保存文件
        project_doc_dir = PROJECTS_DIR / project_id / "documents"
        project_doc_dir.mkdir(parents=True, exist_ok=True)
        file_path = project_doc_dir / unique_filename
        
        with open(file_path, 'wb') as f:
            f.write(file_content)
        
        # 检测文件类型
        mime_types = {
            '.txt': 'text/plain',
            '.md': 'text/markdown',
            '.pdf': 'application/pdf',
            '.doc': 'application/msword',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.xls': 'application/vnd.ms-excel',
            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            '.json': 'application/json',
            '.yaml': 'application/x-yaml',
            '.yml': 'application/x-yaml',
            '.py': 'text/x-python',
            '.js': 'text/javascript',
            '.ts': 'text/typescript',
        }
        file_type = mime_types.get(file_ext.lower(), 'application/octet-stream')
        
        # 创建文档记录
        doc = ProjectDocument(
            filename=unique_filename,
            original_name=filename,
            file_path=str(file_path),
            file_size=len(file_content),
            file_type=file_type,
            document_type=document_type,
            project_id=project_id,
            description=description,
            uploaded_by=uploaded_by
        )
        
        # 读取内容预览
        if file_ext.lower() in ['.txt', '.md', '.json', '.yaml', '.yml', '.py', '.js', '.ts']:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    doc.content_preview = f.read(1000)
            except:
                pass
        
        self._documents[doc.id] = doc
        project.documents.append(doc.id)
        project.stats["total_documents"] += 1
        self._save()
        
        logger.info(f"📄 上传文档: {filename} (项目: {project.name})")
        return doc
    
    async def parse_document_to_tasks(
        self,
        document_id: str,
        auto_create: bool = True
    ) -> List[ProjectTask]:
        """解析文档生成任务"""
        doc = self._documents.get(document_id)
        if not doc:
            return []
        
        # 解析文档
        tasks = await self._parser.parse_document(doc, doc.project_id)
        
        if auto_create:
            project = self._projects.get(doc.project_id)
            if project:
                for task in tasks:
                    self._tasks[task.id] = task
                    project.tasks.append(task.id)
                    doc.parsed_tasks.append(task.id)
                
                doc.parsed = True
                project.stats["total_tasks"] += len(tasks)
                self._save()
        
        logger.info(f"📋 解析文档生成 {len(tasks)} 个任务: {doc.original_name}")
        return tasks
    
    def get_document(self, document_id: str) -> Optional[ProjectDocument]:
        """获取文档"""
        return self._documents.get(document_id)
    
    def delete_document(self, document_id: str) -> bool:
        """删除文档"""
        if document_id not in self._documents:
            return False
        
        doc = self._documents[document_id]
        project = self._projects.get(doc.project_id)
        
        # 删除文件
        if Path(doc.file_path).exists():
            Path(doc.file_path).unlink()
        
        # 更新项目
        if project and document_id in project.documents:
            project.documents.remove(document_id)
            project.stats["total_documents"] -= 1
        
        del self._documents[document_id]
        self._save()
        
        return True
    
    def list_documents(self, project_id: str = None) -> List[ProjectDocument]:
        """列出文档"""
        docs = list(self._documents.values())
        if project_id:
            docs = [d for d in docs if d.project_id == project_id]
        return docs
    
    # ============== 统计 ==============
    
    def get_stats(self) -> Dict:
        """获取统计"""
        return {
            "total_projects": len(self._projects),
            "total_tasks": len(self._tasks),
            "total_documents": len(self._documents),
            "by_status": {
                "projects": {
                    s.value: len([p for p in self._projects.values() if p.status == s])
                    for s in ProjectStatus
                },
                "tasks": {
                    s.value: len([t for t in self._tasks.values() if t.status == s])
                    for s in TaskStatus
                }
            }
        }


# ============== 全局实例 ==============

project_manager = ProjectManager()