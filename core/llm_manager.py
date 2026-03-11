# core/llm_manager.py
"""LLM 多模型管理器

支持分级模型和故障切换。
"""

import os
import yaml
from typing import Dict, List, Optional
from pathlib import Path

from .llm_client import LLMClient
from utils import get_logger

logger = get_logger("llm_manager")


class LLMManager:
    """LLM 多模型管理器
    
    从配置文件加载模型，支持分级和故障切换。
    """
    
    def __init__(self, config_path: str = "llm_config.yaml"):
        """初始化管理器
        
        Args:
            config_path: 配置文件路径
        """
        self.config_path = Path(config_path)
        self.config = {}
        self.clients: Dict[str, List[LLMClient]] = {
            "light": [],
            "standard": [],
            "advanced": []
        }
        self.usage_map: Dict[str, str] = {}
        
        self._load_config()
        self._init_clients()
    
    def _load_config(self):
        """加载配置文件"""
        if not self.config_path.exists():
            logger.warning(f"配置文件不存在: {self.config_path}")
            return
        
        with open(self.config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f) or {}
        
        # 加载用途映射
        self.usage_map = self.config.get("usage", {})
        logger.debug(f"用途映射: {self.usage_map}")
    
    def _init_clients(self):
        """初始化所有客户端"""
        models_config = self.config.get("models", {})
        
        for tier in ["light", "standard", "advanced"]:
            tier_models = models_config.get(tier, [])
            
            for model_cfg in tier_models:
                try:
                    client = self._create_client(model_cfg)
                    if client:
                        self.clients[tier].append(client)
                        logger.info(f"初始化 {tier} 模型: {model_cfg.get('model')}")
                except Exception as e:
                    logger.error(f"初始化模型失败 {model_cfg}: {e}")
    
    def _create_client(self, model_cfg: dict) -> Optional[LLMClient]:
        """创建单个客户端"""
        api_key_env = model_cfg.get("api_key_env")
        api_key = os.getenv(api_key_env, "")
        
        if not api_key:
            logger.warning(f"API Key 未配置: {api_key_env}")
            return None
        
        return LLMClient(
            api_key=api_key,
            base_url=model_cfg.get("base_url"),
            model=model_cfg.get("model"),
            api_name=model_cfg.get("api_name"),
            name=model_cfg.get("name")
        )
    
    def get_client(self, usage: str = "default") -> Optional[LLMClient]:
        """获取指定用途的客户端
        
        Args:
            usage: 用途名称（如 router, schedule, inbox）
            
        Returns:
            LLMClient 实例，如果没有可用客户端返回 None
        """
        tier = self.usage_map.get(usage, self.usage_map.get("default", "standard"))
        clients = self.clients.get(tier, [])
        
        if clients:
            return clients[0]  # 返回第一个可用的
        
        # 降级：尝试 standard
        if tier != "standard" and self.clients.get("standard"):
            logger.warning(f"用途 {usage} 无可用 {tier} 模型，降级到 standard")
            return self.clients["standard"][0]
        
        logger.error(f"没有可用的模型: usage={usage}, tier={tier}")
        return None
    
    def call_with_fallback(self, usage: str, messages: list, 
                           tools: list = None, **kwargs) -> dict:
        """调用模型，失败时自动切换备用
        
        Args:
            usage: 用途名称
            messages: 消息列表
            tools: 工具列表（可选）
            
        Returns:
            LLM 响应
        """
        tier = self.usage_map.get(usage, self.usage_map.get("default", "standard"))
        clients = self.clients.get(tier, [])
        
        # 没有客户端时尝试降级
        if not clients:
            clients = self.clients.get("standard", [])
        
        last_error = None
        error_details = []
        
        for i, client in enumerate(clients):
            try:
                return client.chat(messages, tools=tools, **kwargs)
            except Exception as e:
                error_info = f"[{tier.upper()}] {client.api_name} ({client.name}/{client.model}): {e}"
                logger.warning(f"模型 {i+1} 调用失败 - {error_info}")
                error_details.append(error_info)
                last_error = e
                continue
        
        # 所有模型都失败了，抛出详细错误
        error_summary = "\n".join([f"  • {detail}" for detail in error_details])
        raise RuntimeError(
            f"所有模型调用失败 (用途:{usage}, 层级:{tier})\n"
            f"{error_summary}\n"
            f"最后错误: {last_error}"
        )
    
    def get_tier(self, usage: str) -> str:
        """获取用途对应的级别"""
        return self.usage_map.get(usage, "standard")
