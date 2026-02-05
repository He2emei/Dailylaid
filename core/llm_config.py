# core/llm_config.py
"""LLM 多模型配置管理"""

import os
import yaml
from typing import Dict, Optional
from dataclasses import dataclass

from utils import get_logger

logger = get_logger("llm_config")


@dataclass
class ProviderConfig:
    """API 提供商配置"""
    name: str
    base_url: str
    api_key: str


@dataclass
class ModelConfig:
    """模型配置"""
    level: str
    model: str
    description: str


class LLMConfig:
    """LLM 配置管理器
    
    支持多提供商、多模型分级配置。
    """
    
    def __init__(self, config_path: str = "llm_config.yaml"):
        """初始化配置
        
        Args:
            config_path: 配置文件路径
        """
        self.config_path = config_path
        self._providers: Dict[str, ProviderConfig] = {}
        self._models: Dict[str, ModelConfig] = {}
        self._active_provider: str = ""
        self._default_level: str = "standard"
        
        self._load_config()
    
    def _load_config(self):
        """加载配置文件"""
        if not os.path.exists(self.config_path):
            logger.warning(f"配置文件不存在: {self.config_path}，使用默认配置")
            self._use_default_config()
            return
        
        with open(self.config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        
        # 解析提供商配置
        for name, provider_data in config.get("providers", {}).items():
            api_key_env = provider_data.get("api_key_env", "")
            api_key = os.getenv(api_key_env, "")
            
            self._providers[name] = ProviderConfig(
                name=name,
                base_url=provider_data.get("base_url", ""),
                api_key=api_key
            )
        
        # 解析模型配置
        for level, model_data in config.get("models", {}).items():
            self._models[level] = ModelConfig(
                level=level,
                model=model_data.get("model", ""),
                description=model_data.get("description", "")
            )
        
        # 读取激活的提供商（支持环境变量覆盖）
        self._active_provider = os.getenv(
            "LLM_ACTIVE_PROVIDER",
            config.get("active_provider", "")
        )
        
        # 读取默认模型级别
        self._default_level = config.get("default_level", "standard")
        
        logger.info(f"LLM 配置加载完成: 提供商={self._active_provider}, 默认级别={self._default_level}")
    
    def _use_default_config(self):
        """使用默认配置（从环境变量）"""
        self._providers["default"] = ProviderConfig(
            name="default",
            base_url=os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"),
            api_key=os.getenv("LLM_API_KEY", "")
        )
        self._models["standard"] = ModelConfig(
            level="standard",
            model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
            description="默认模型"
        )
        self._active_provider = "default"
        self._default_level = "standard"
    
    @property
    def active_provider(self) -> ProviderConfig:
        """获取当前激活的提供商"""
        return self._providers.get(self._active_provider)
    
    def get_model(self, level: str = None) -> tuple:
        """获取指定级别的模型配置
        
        Args:
            level: 模型级别 (advanced/standard/light)，默认使用 default_level
            
        Returns:
            (base_url, api_key, model_name)
        """
        level = level or self._default_level
        
        provider = self.active_provider
        if not provider:
            raise ValueError(f"未找到提供商: {self._active_provider}")
        
        model_config = self._models.get(level)
        if not model_config:
            # 回退到默认级别
            model_config = self._models.get(self._default_level)
            if not model_config:
                raise ValueError(f"未找到模型配置: {level}")
        
        return provider.base_url, provider.api_key, model_config.model
    
    def get_client(self, level: str = None):
        """获取指定级别的 LLM 客户端
        
        Args:
            level: 模型级别
            
        Returns:
            LLMClient 实例
        """
        from .llm_client import LLMClient
        
        base_url, api_key, model = self.get_model(level)
        return LLMClient(api_key=api_key, base_url=base_url, model=model)
    
    def list_models(self) -> Dict[str, str]:
        """列出所有配置的模型"""
        return {
            level: f"{config.model} ({config.description})"
            for level, config in self._models.items()
        }
    
    def list_providers(self) -> list:
        """列出所有配置的提供商"""
        return list(self._providers.keys())
