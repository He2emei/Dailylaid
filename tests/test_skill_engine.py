# tests/test_skill_engine.py
"""SkillEngine 单元测试"""

import os
import pytest

from core.skill_engine import SkillEngine, SkillMeta, SkillContent


# ────────────────────── fixtures ──────────────────────

@pytest.fixture
def skills_dir(tmp_path):
    """创建一个临时 skills/ 目录，带两个合法 Skill 和一个异常情况"""

    # 正常 Skill：schedule
    schedule_dir = tmp_path / "schedule"
    schedule_dir.mkdir()
    (schedule_dir / "SKILL.md").write_text(
        "---\n"
        "name: schedule\n"
        "description: 管理未来的日程安排。当用户提到\"明天\"等词时使用。\n"
        "---\n\n"
        "# 日程管理\n\n## 规则\n1. 使用 YYYY-MM-DD HH:MM 格式\n",
        encoding="utf-8"
    )

    # 正常 Skill：inbox（带 references 目录）
    inbox_dir = tmp_path / "inbox"
    inbox_dir.mkdir()
    (inbox_dir / "SKILL.md").write_text(
        "---\n"
        "name: inbox\n"
        "description: 收集箱，保存暂时无法分类的内容。\n"
        "---\n\n"
        "# 收集箱\n\n## 规则\n1. 保留原始内容\n",
        encoding="utf-8"
    )
    ref_dir = inbox_dir / "references"
    ref_dir.mkdir()
    (ref_dir / "priority_guide.md").write_text(
        "## 优先级指南\n- high: 紧急\n- medium: 普通\n- low: 随意\n",
        encoding="utf-8"
    )

    # 异常情况：目录存在但没有 SKILL.md
    empty_dir = tmp_path / "empty_skill"
    empty_dir.mkdir()

    # 异常情况：是个文件而非目录
    (tmp_path / "not_a_dir.txt").write_text("test", encoding="utf-8")

    return tmp_path


@pytest.fixture
def engine(skills_dir):
    e = SkillEngine(str(skills_dir))
    e.discover()
    return e


# ────────────────────── 测试 discover ──────────────────────

class TestDiscover:
    def test_discovers_valid_skills(self, engine):
        """应能正确发现两个合法 Skill"""
        names = engine.all_names()
        assert "schedule" in names
        assert "inbox" in names

    def test_skips_dir_without_skill_md(self, engine):
        """没有 SKILL.md 的目录应被跳过"""
        assert "empty_skill" not in engine.all_names()

    def test_skips_files(self, engine):
        """文件（非目录）不应被识别为 Skill"""
        assert "not_a_dir.txt" not in engine.all_names()

    def test_nonexistent_skills_dir(self, tmp_path):
        """Skills 目录不存在时应优雅返回空列表"""
        e = SkillEngine(str(tmp_path / "nonexistent"))
        result = e.discover()
        assert result == []

    def test_meta_fields(self, engine):
        """解析出的元数据字段正确"""
        meta = engine._index["schedule"]
        assert isinstance(meta, SkillMeta)
        assert meta.name == "schedule"
        assert "明天" in meta.description


# ────────────────────── 测试 get_instructions ──────────────────────

class TestGetInstructions:
    def test_returns_body_without_frontmatter(self, engine):
        """返回的正文不应含 YAML frontmatter"""
        instructions = engine.get_instructions("schedule")
        assert instructions is not None
        assert "---" not in instructions
        assert "# 日程管理" in instructions
        assert "YYYY-MM-DD HH:MM" in instructions

    def test_returns_none_for_unknown_skill(self, engine):
        """未知 Skill 应返回 None"""
        assert engine.get_instructions("nonexistent") is None

    def test_caches_result(self, engine):
        """第二次调用应使用缓存，不重新读文件"""
        instructions1 = engine.get_instructions("schedule")
        instructions2 = engine.get_instructions("schedule")
        assert instructions1 == instructions2
        assert "schedule" in engine._cache


# ────────────────────── 测试 build_skills_list ──────────────────────

class TestBuildSkillsList:
    def test_contains_all_skills(self, engine):
        """技能清单应包含所有已发现的 Skill"""
        skills_list = engine.build_skills_list()
        assert "schedule" in skills_list
        assert "inbox" in skills_list

    def test_format(self, engine):
        """每行格式为 '- name: description'"""
        for line in engine.build_skills_list().split("\n"):
            assert line.startswith("- ")
            assert ": " in line


# ────────────────────── 测试 load_reference ──────────────────────

class TestLoadReference:
    def test_loads_existing_reference(self, engine):
        """能正确加载 references/ 下的文件"""
        content = engine.load_reference("inbox", "priority_guide.md")
        assert content is not None
        assert "优先级指南" in content

    def test_returns_none_for_missing_reference(self, engine):
        """参考文件不存在时返回 None"""
        assert engine.load_reference("inbox", "nonexistent.md") is None

    def test_caches_reference(self, engine):
        """参考文件应被缓存"""
        engine.load_reference("inbox", "priority_guide.md")
        cached = engine._cache.get("inbox")
        assert cached is not None
        assert "priority_guide.md" in cached.references


# ────────────────────── 测试 YAML frontmatter 解析 ──────────────────────

class TestFrontmatterParsing:
    def test_split_frontmatter(self):
        content = "---\nname: test\ndescription: 测试\n---\n\n# 正文\n内容在这里\n"
        _, body = SkillEngine._split_frontmatter(content)
        assert "# 正文" in body
        assert "name:" not in body

    def test_no_frontmatter(self):
        content = "# 没有 frontmatter\n内容"
        _, body = SkillEngine._split_frontmatter(content)
        assert "没有 frontmatter" in body

    def test_parse_frontmatter_dict(self, skills_dir):
        skill_md = str(skills_dir / "schedule" / "SKILL.md")
        fm = SkillEngine._parse_frontmatter(skill_md)
        assert fm["name"] == "schedule"
        assert "明天" in fm["description"]
