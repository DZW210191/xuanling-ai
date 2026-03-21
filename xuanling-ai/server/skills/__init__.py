"""
玄灵AI Skills 系统 - 动态加载技能模块
支持热加载、依赖管理、技能生命周期
"""
import os
import sys
import json
import importlib
import importlib.util
import logging
import asyncio
import threading
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
import hashlib

logger = logging.getLogger("玄灵AI.Skills")

# ============== 技能定义 ==============

@dataclass
class SkillDependency:
    """技能依赖"""
    name: str
    version: Optional[str] = None
    optional: bool = False

@dataclass 
class SkillConfig:
    """技能配置"""
    enabled: bool = True
    priority: int = 100  # 加载优先级，数字越小越先加载
    auto_start: bool = True
    timeout: int = 30
    max_retries: int = 3
    params: Dict[str, Any] = field(default_factory=dict)

@dataclass
class SkillMetadata:
    """技能元数据"""
    name: str
    version: str = "1.0.0"
    description: str = ""
    author: str = ""
    category: str = "general"
    tags: List[str] = field(default_factory=list)
    dependencies: List[SkillDependency] = field(default_factory=list)
    requires_auth: bool = False
    dangerous: bool = False
    config: SkillConfig = field(default_factory=SkillConfig)
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "category": self.category,
            "tags": self.tags,
            "dependencies": [{"name": d.name, "version": d.version, "optional": d.optional} for d in self.dependencies],
            "requires_auth": self.requires_auth,
            "dangerous": self.dangerous,
            "config": {
                "enabled": self.config.enabled,
                "priority": self.config.priority,
                "auto_start": self.config.auto_start
            }
        }

@dataclass
class SkillState:
    """技能运行状态"""
    loaded: bool = False
    running: bool = False
    error: Optional[str] = None
    last_error_time: Optional[datetime] = None
    start_time: Optional[datetime] = None
    reload_count: int = 0
    execution_count: int = 0
    last_execution: Optional[datetime] = None


class SkillBase:
    """技能基类 - 所有技能必须继承"""
    
    # 子类必须定义
    metadata: SkillMetadata = None
    
    def __init__(self, skill_manager: 'SkillManager' = None):
        self.skill_manager = skill_manager
        self._state = SkillState()
        self._handlers: Dict[str, Callable] = {}
        self._background_tasks: List[asyncio.Task] = []
    
    @property
    def name(self) -> str:
        return self.metadata.name if self.metadata else "unknown"
    
    @property
    def state(self) -> SkillState:
        return self._state
    
    async def on_load(self):
        """加载时调用 - 初始化资源"""
        pass
    
    async def on_unload(self):
        """卸载时调用 - 清理资源"""
        pass
    
    async def on_start(self):
        """启动时调用 - 开始后台任务"""
        pass
    
    async def on_stop(self):
        """停止时调用 - 停止后台任务"""
        # 取消所有后台任务
        for task in self._background_tasks:
            if not task.done():
                task.cancel()
        self._background_tasks.clear()
    
    async def execute(self, action: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """执行技能动作"""
        if not self._state.loaded:
            return {"success": False, "error": f"技能 {self.name} 未加载"}
        
        handler = self._handlers.get(action)
        if not handler:
            return {"success": False, "error": f"未知动作: {action}"}
        
        try:
            self._state.execution_count += 1
            self._state.last_execution = datetime.now()
            
            if asyncio.iscoroutinefunction(handler):
                result = await handler(params or {})
            else:
                result = handler(params or {})
            
            return {"success": True, "result": result}
        except Exception as e:
            logger.error(f"技能 {self.name} 执行 {action} 失败: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
    
    def register_handler(self, action: str, handler: Callable):
        """注册动作处理器"""
        self._handlers[action] = handler
        logger.info(f"  ✅ 注册动作: {action}")
    
    def create_background_task(self, coro):
        """创建后台任务"""
        task = asyncio.create_task(coro)
        self._background_tasks.append(task)
        return task


# ============== 技能管理器 ==============

class SkillManager:
    """技能管理器 - 动态加载、生命周期管理"""
    
    def __init__(self, skills_dir: str = None):
        self.skills_dir = Path(skills_dir or os.path.dirname(__file__))
        self._skills: Dict[str, SkillBase] = {}
        self._skill_files: Dict[str, Path] = {}  # 技能名 -> 文件路径
        self._file_hashes: Dict[str, str] = {}  # 文件路径 -> 哈希（用于热重载）
        self._lock = threading.RLock()
        self._tool_registry = None
        self._audit_logger = None
        
    def set_tool_registry(self, registry):
        """设置工具注册中心"""
        self._tool_registry = registry
    
    def set_audit_logger(self, logger):
        """设置审计日志"""
        self._audit_logger = logger
    
    def _get_file_hash(self, path: Path) -> str:
        """计算文件哈希"""
        with open(path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()
    
    def discover_skills(self) -> List[Path]:
        """发现所有技能文件"""
        skill_files = []
        
        # 扫描技能目录
        if self.skills_dir.exists():
            for file in self.skills_dir.glob("*.py"):
                if file.name.startswith("_") or file.name == "__init__.py":
                    continue
                skill_files.append(file)
        
        # 扫描子目录（每个子目录是一个技能包）
        for subdir in self.skills_dir.iterdir():
            if subdir.is_dir() and not subdir.name.startswith("_"):
                init_file = subdir / "__init__.py"
                if init_file.exists():
                    skill_files.append(init_file)
        
        logger.info(f"🔍 发现 {len(skill_files)} 个技能文件")
        return skill_files
    
    async def load_skill(self, skill_path: Path) -> Optional[str]:
        """加载单个技能"""
        try:
            # 计算模块名
            if skill_path.name == "__init__.py":
                module_name = f"skills.{skill_path.parent.name}"
            else:
                module_name = f"skills.{skill_path.stem}"
            
            # 保存文件哈希
            self._file_hashes[str(skill_path)] = self._get_file_hash(skill_path)
            
            # 动态导入
            spec = importlib.util.spec_from_file_location(module_name, skill_path)
            if not spec or not spec.loader:
                logger.error(f"无法加载模块: {skill_path}")
                return None
            
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            
            # 查找技能类
            skill_class = None
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (isinstance(attr, type) and 
                    issubclass(attr, SkillBase) and 
                    attr != SkillBase and
                    hasattr(attr, 'metadata')):
                    skill_class = attr
                    break
            
            if not skill_class:
                logger.warning(f"未找到技能类: {skill_path}")
                return None
            
            # 实例化技能
            skill_instance = skill_class(self)
            skill_name = skill_instance.name
            
            # 检查依赖
            if not await self._check_dependencies(skill_instance):
                logger.error(f"技能 {skill_name} 依赖检查失败")
                return None
            
            # 加载技能
            await skill_instance.on_load()
            skill_instance._state.loaded = True
            
            # 存储技能
            with self._lock:
                self._skills[skill_name] = skill_instance
                self._skill_files[skill_name] = skill_path
            
            # 注册工具
            if self._tool_registry:
                await self._register_tools(skill_instance)
            
            logger.info(f"✅ 加载技能: {skill_name} v{skill_instance.metadata.version}")
            
            # 记录审计日志
            if self._audit_logger:
                await self._audit_logger.log(
                    action="skill_load",
                    resource=skill_name,
                    details={"version": skill_instance.metadata.version, "path": str(skill_path)}
                )
            
            return skill_name
            
        except Exception as e:
            logger.error(f"加载技能失败 {skill_path}: {e}", exc_info=True)
            return None
    
    async def _check_dependencies(self, skill: SkillBase) -> bool:
        """检查技能依赖"""
        for dep in skill.metadata.dependencies:
            if dep.name.startswith("python:"):
                # Python 包依赖
                package = dep.name[7:]
                try:
                    importlib.import_module(package)
                except ImportError:
                    if not dep.optional:
                        logger.error(f"缺少依赖: {package}")
                        return False
                    logger.warning(f"可选依赖缺失: {package}")
            elif dep.name in self._skills:
                # 技能依赖
                pass  # 已加载
            elif not dep.optional:
                logger.error(f"缺少技能依赖: {dep.name}")
                return False
        return True
    
    async def _register_tools(self, skill: SkillBase):
        """注册技能的工具"""
        from tools import ToolDefinition, tool_registry
        
        # 遍历技能的动作，注册为工具
        for action, handler in skill._handlers.items():
            tool_name = f"{skill.name}_{action}"
            
            # 从处理器获取参数定义（如果有）
            params = getattr(handler, '_tool_params', {
                "type": "object",
                "properties": {}
            })
            
            # 创建包装函数 - 使用工厂函数正确捕获变量
            def make_wrapper(h):
                async def wrapper(**kwargs):
                    if asyncio.iscoroutinefunction(h):
                        return await h(kwargs)
                    return h(kwargs)
                return wrapper
            
            tool_registry.register(ToolDefinition(
                name=tool_name,
                description=f"{skill.metadata.description} - {action}",
                parameters=params,
                handler=make_wrapper(handler),
                category=skill.metadata.category,
                requires_auth=skill.metadata.requires_auth,
                dangerous=skill.metadata.dangerous
            ))
    
    async def unload_skill(self, name: str) -> bool:
        """卸载技能"""
        with self._lock:
            if name not in self._skills:
                return False
            
            skill = self._skills[name]
            
            try:
                # 停止技能
                if skill._state.running:
                    await skill.on_stop()
                
                # 卸载
                await skill.on_unload()
                
                # 移除工具
                if self._tool_registry:
                    for action in skill._handlers:
                        tool_name = f"{name}_{action}"
                        self._tool_registry.unregister(tool_name)
                
                del self._skills[name]
                if name in self._skill_files:
                    del self._skill_files[name]
                
                logger.info(f"🗑️ 卸载技能: {name}")
                
                # 审计日志
                if self._audit_logger:
                    await self._audit_logger.log(
                        action="skill_unload",
                        resource=name
                    )
                
                return True
                
            except Exception as e:
                logger.error(f"卸载技能失败 {name}: {e}", exc_info=True)
                return False
    
    async def reload_skill(self, name: str) -> bool:
        """热重载技能"""
        if name not in self._skill_files:
            return False
        
        skill_path = self._skill_files[name]
        
        # 检查文件是否变化
        current_hash = self._get_file_hash(skill_path)
        if current_hash == self._file_hashes.get(str(skill_path)):
            logger.info(f"技能 {name} 未变化，跳过重载")
            return True
        
        # 卸载旧版本
        await self.unload_skill(name)
        
        # 加载新版本
        loaded_name = await self.load_skill(skill_path)
        if loaded_name:
            self._skills[loaded_name]._state.reload_count += 1
            logger.info(f"🔄 热重载技能: {name}")
            return True
        
        return False
    
    async def load_all(self) -> Dict[str, bool]:
        """加载所有技能"""
        results = {}
        skill_files = self.discover_skills()
        
        # 按优先级排序
        # TODO: 实现依赖解析和优先级排序
        
        for skill_file in skill_files:
            name = await self.load_skill(skill_file)
            results[skill_file.name] = name is not None
        
        return results
    
    async def start_skill(self, name: str) -> bool:
        """启动技能"""
        if name not in self._skills:
            return False
        
        skill = self._skills[name]
        
        if skill._state.running:
            return True
        
        try:
            await skill.on_start()
            skill._state.running = True
            skill._state.start_time = datetime.now()
            logger.info(f"▶️ 启动技能: {name}")
            return True
        except Exception as e:
            skill._state.error = str(e)
            skill._state.last_error_time = datetime.now()
            logger.error(f"启动技能失败 {name}: {e}", exc_info=True)
            return False
    
    async def stop_skill(self, name: str) -> bool:
        """停止技能"""
        if name not in self._skills:
            return False
        
        skill = self._skills[name]
        
        if not skill._state.running:
            return True
        
        try:
            await skill.on_stop()
            skill._state.running = False
            logger.info(f"⏹️ 停止技能: {name}")
            return True
        except Exception as e:
            logger.error(f"停止技能失败 {name}: {e}", exc_info=True)
            return False
    
    def get_skill(self, name: str) -> Optional[SkillBase]:
        """获取技能实例"""
        return self._skills.get(name)
    
    def list_skills(self) -> List[Dict]:
        """列出所有技能"""
        result = []
        for name, skill in self._skills.items():
            result.append({
                "name": name,
                "metadata": skill.metadata.to_dict(),
                "state": {
                    "loaded": skill._state.loaded,
                    "running": skill._state.running,
                    "error": skill._state.error,
                    "execution_count": skill._state.execution_count,
                    "reload_count": skill._state.reload_count
                }
            })
        return result
    
    async def execute(self, skill_name: str, action: str, params: Dict = None) -> Dict:
        """执行技能动作"""
        skill = self.get_skill(skill_name)
        if not skill:
            return {"success": False, "error": f"技能不存在: {skill_name}"}
        
        # 审计日志
        if self._audit_logger:
            await self._audit_logger.log(
                action=f"skill_execute:{skill_name}.{action}",
                resource=skill_name,
                details={"action": action, "params": params}
            )
        
        return await skill.execute(action, params)


# 全局技能管理器
skill_manager = SkillManager()


# ============== 装饰器 ==============

def skill_action(name: str, params: Dict = None):
    """技能动作装饰器"""
    def decorator(func):
        func._action_name = name
        func._tool_params = params or {
            "type": "object",
            "properties": {}
        }
        return func
    return decorator


def tool_params(schema: Dict):
    """工具参数定义装饰器"""
    def decorator(func):
        func._tool_params = schema
        return func
    return decorator


# ============== 示例技能 ==============

class ExampleSkill(SkillBase):
    """示例技能"""
    
    metadata = SkillMetadata(
        name="example",
        version="1.0.0",
        description="示例技能，展示技能系统功能",
        author="玄灵AI",
        category="demo",
        tags=["example", "demo"],
        config=SkillConfig(enabled=True, priority=100)
    )
    
    async def on_load(self):
        """加载时注册动作"""
        self.register_handler("hello", self.hello)
        self.register_handler("echo", self.echo)
        logger.info(f"示例技能加载完成")
    
    async def hello(self, params: Dict) -> Dict:
        """问候"""
        name = params.get("name", "用户")
        return {"message": f"你好，{name}！我是示例技能"}
    
    async def echo(self, params: Dict) -> Dict:
        """回声"""
        message = params.get("message", "")
        return {"echo": message, "length": len(message)}