# utils/logger.py
"""日志工具模块"""

import logging
import sys
from datetime import datetime
from pathlib import Path


def setup_logger(
    name: str = "dailylaid",
    level: int = logging.INFO,
    log_file: str = None,
    console: bool = True
) -> logging.Logger:
    """配置并返回一个 Logger 实例
    
    Args:
        name: 日志器名称
        level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: 日志文件路径 (可选)
        console: 是否输出到控制台
        
    Returns:
        配置好的 Logger 实例
    """
    logger = logging.getLogger(name)
    
    # 避免重复添加 handler
    if logger.handlers:
        return logger
    
    logger.setLevel(level)
    
    # 日志格式
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # 简洁格式 (用于控制台)
    console_formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%H:%M:%S"
    )
    
    # 控制台输出
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
    
    # 文件输出
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


# 创建默认的全局 logger
_logger = None


def get_logger(name: str = None) -> logging.Logger:
    """获取 Logger 实例
    
    Args:
        name: 可选的子日志器名称
        
    Returns:
        Logger 实例
    """
    global _logger
    
    if _logger is None:
        _logger = setup_logger()
    
    if name:
        return _logger.getChild(name)
    
    return _logger


def init_logger(level: str = "INFO", log_file: str = None):
    """初始化全局日志器
    
    Args:
        level: 日志级别字符串 ("DEBUG", "INFO", "WARNING", "ERROR")
        log_file: 日志文件路径
        
    注意: 此函数会强制重建 logger，即使之前已创建
    """
    global _logger
    
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL
    }
    
    log_level = level_map.get(level.upper(), logging.INFO)
    
    # 如果已存在 logger，清除旧的 handlers
    if _logger is not None:
        for handler in _logger.handlers[:]:
            handler.close()
            _logger.removeHandler(handler)
    
    # 重新配置
    _logger = setup_logger(level=log_level, log_file=log_file)
    
    return _logger

