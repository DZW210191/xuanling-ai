"""
Skills - 技能系统
"""
from typing import Dict, Any, Callable, List
from dataclasses import dataclass
import yaml
import importlib.util
from pathlib import Path


@dataclass
class Skill:
    """技能定义"""
    name: str
    description: str
    version: str
    tools: List[str]
    handler: Any
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "tools": self.tools
        }


class SkillLoader:
    """技能加载器"""
    
    def load(self, skill_path: str) -> Skill:
        """加载单个技能"""
        config_file = Path(skill_path) / "skill.yaml"
        if not config_file.exists():
            raise FileNotFoundError(f"skill.yaml not found in {skill_path}")
        
        with open(config_file) as f:
            config = yaml.safe_load(f)
        
        return Skill(
            name=config.get("name", ""),
            description=config.get("description", ""),
            version=config.get("version", "1.0.0"),
            tools=config.get("tools", []),
            handler=None
        )


class SkillRegistry:
    """技能注册表"""
    
    def __init__(self):
        self.skills: Dict[str, Skill] = {}
    
    def register(self, skill: Skill):
        """注册技能"""
        self.skills[skill.name] = skill
    
    async def load_from_dir(self, dir_path: str):
        """从目录加载技能"""
        skills_dir = Path(dir_path)
        if not skills_dir.exists():
            return
        
        for skill_dir in skills_dir.iterdir():
            if skill_dir.is_dir():
                try:
                    skill = self.loader.load(str(skill_dir))
                    self.register(skill)
                except Exception as e:
                    print(f"Failed to load skill {skill_dir}: {e}")
    
    async def execute(self, skill_name: str, action: str, **kwargs) -> Any:
        """执行技能"""
        skill = self.skills.get(skill_name)
        if not skill:
            raise ValueError(f"Skill {skill_name} not found")
        return {"status": "ok", "skill": skill.name}
    
    def get_skills(self) -> List[Dict]:
        """获取所有技能"""
        return [s.to_dict() for s in self.skills.values()]
