# core/skill_engine.py
"""Skill 引擎 — 从文件系统加载模块级 SOP 指令"""

import os
import re
import yaml
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from utils import get_logger

logger = get_logger("skill_engine")


@dataclass
class SkillMeta:
    """Skill 元数据（从 YAML frontmatter 解析）"""
    name: str
    description: str
    path: str  # Skill 目录的绝对路径


@dataclass
class SkillContent:
    """Skill 完整内容（激活后加载）"""
    meta: SkillMeta
    instructions: str               # SKILL.md 正文（去掉 frontmatter 后的 Markdown）
    references: Dict[str, str] = field(default_factory=dict)  # 按需加载的参考文件缓存


class SkillEngine:
    """Skill 引擎
    
    负责 Skill 的发现（Discover）、索引（Index）、激活（Activate）、
    按需加载资源（Load References）。
    
    使用方式:
        engine = SkillEngine(skills_dir="skills/")
        engine.discover()
        instructions = engine.get_instructions("schedule")
    """

    def __init__(self, skills_dir: str):
        """
        Args:
            skills_dir: skills/ 目录的路径（绝对路径或相对路径均可）
        """
        self.skills_dir = os.path.abspath(skills_dir)
        self._index: Dict[str, SkillMeta] = {}   # name -> SkillMeta
        self._cache: Dict[str, SkillContent] = {} # name -> SkillContent（已激活的缓存）

    # ───────────────────────────── 公开 API ─────────────────────────────

    def discover(self) -> List[SkillMeta]:
        """扫描 skills/ 目录，建立元数据索引。
        
        只解析 YAML frontmatter，不读取正文（低成本）。
        同名 Skill 不会重复注册（以先扫描到的为准）。
        
        Returns:
            已发现的 SkillMeta 列表
        """
        if not os.path.isdir(self.skills_dir):
            logger.warning(f"Skills 目录不存在: {self.skills_dir}")
            return []

        for entry in sorted(os.listdir(self.skills_dir)):
            skill_dir = os.path.join(self.skills_dir, entry)
            skill_md = os.path.join(skill_dir, "SKILL.md")

            if not (os.path.isdir(skill_dir) and os.path.exists(skill_md)):
                continue

            try:
                fm = self._parse_frontmatter(skill_md)
                name = fm.get("name") or entry
                description = fm.get("description", "")

                meta = SkillMeta(name=name, description=description, path=skill_dir)
                self._index[meta.name] = meta
                logger.info(f"发现 Skill: {meta.name}")
            except Exception as e:
                logger.error(f"解析 Skill 失败 [{entry}]: {e}")

        return list(self._index.values())

    def get_instructions(self, skill_name: str) -> Optional[str]:
        """获取 Skill 的正文指令（激活阶段）。
        
        第一次调用时读取文件并缓存；后续调用直接返回缓存。
        
        Args:
            skill_name: Skill 名称（与 SKILL.md 中的 name 字段一致）
            
        Returns:
            SKILL.md 正文字符串，或 None（Skill 不存在时）
        """
        if skill_name in self._cache:
            return self._cache[skill_name].instructions

        meta = self._index.get(skill_name)
        if not meta:
            logger.warning(f"Skill 未找到: {skill_name}")
            return None

        try:
            skill_md = os.path.join(meta.path, "SKILL.md")
            content = self._read_file(skill_md)
            _, instructions = self._split_frontmatter(content)

            self._cache[skill_name] = SkillContent(meta=meta, instructions=instructions)
            logger.debug(f"已激活 Skill: {skill_name}")
            return instructions
        except Exception as e:
            logger.error(f"加载 Skill [{skill_name}] 失败: {e}")
            return None

    def load_reference(self, skill_name: str, ref_name: str) -> Optional[str]:
        """按需加载 references/ 中的参考文件（带缓存）。
        
        Args:
            skill_name: Skill 名称
            ref_name: 参考文件名（如 "time_format_guide.md"）
            
        Returns:
            文件内容字符串，或 None（文件不存在时）
        """
        # 确保 Skill 已激活（建立 cache 条目）
        if skill_name not in self._cache:
            self.get_instructions(skill_name)

        cached = self._cache.get(skill_name)
        if not cached:
            return None

        if ref_name in cached.references:
            return cached.references[ref_name]  # 已缓存

        ref_path = os.path.join(cached.meta.path, "references", ref_name)
        if os.path.exists(ref_path):
            content = self._read_file(ref_path)
            cached.references[ref_name] = content
            return content

        logger.warning(f"参考文件不存在: {ref_path}")
        return None

    def build_skills_list(self) -> str:
        """构建给路由 LLM 看的技能清单（每个 Skill 一行）。
        
        Returns:
            形如 "- schedule: 管理未来的日程..." 的多行字符串
        """
        lines = [f"- {meta.name}: {meta.description}" for meta in self._index.values()]
        return "\n".join(lines)

    def all_names(self) -> List[str]:
        """返回所有已发现的 Skill 名称列表"""
        return list(self._index.keys())

    # ───────────────────────────── 内部方法 ─────────────────────────────

    @staticmethod
    def _parse_frontmatter(filepath: str) -> dict:
        """解析 SKILL.md 的 YAML frontmatter，返回字典。"""
        content = SkillEngine._read_file(filepath)
        match = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
        if match:
            return yaml.safe_load(match.group(1)) or {}
        return {}

    @staticmethod
    def _split_frontmatter(content: str) -> tuple:
        """将 SKILL.md 内容分离为 (frontmatter_dict, body_str)。"""
        match = re.match(r'^---\s*\n.*?\n---\s*\n(.*)', content, re.DOTALL)
        if match:
            return {}, match.group(1).strip()
        return {}, content.strip()

    @staticmethod
    def _read_file(filepath: str) -> str:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
