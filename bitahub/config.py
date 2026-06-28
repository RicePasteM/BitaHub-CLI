"""Configuration management for BitaHub CLI."""

import json
import os
from pathlib import Path
from typing import Optional

# 配置文件路径
CONFIG_DIR = Path.home() / ".bitahub"
CONFIG_FILE = CONFIG_DIR / "config.json"

# 默认配置
DEFAULT_CONFIG = {
    "base_url": "https://bitahub.ustc.edu.cn",
    "username": None,
    "password": None,
    "cookies": None,
    "token": None,
    "current_project_id": None,
    "current_project_name": None,
    "default_team_id": None,
}


def ensure_config_dir():
    """确保配置目录存在."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> dict:
    """加载配置文件."""
    ensure_config_dir()

    if not CONFIG_FILE.exists():
        return DEFAULT_CONFIG.copy()

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
        # 合并默认配置
        return {**DEFAULT_CONFIG, **config}
    except (json.JSONDecodeError, IOError):
        return DEFAULT_CONFIG.copy()


def save_config(config: dict):
    """保存配置文件."""
    ensure_config_dir()

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def get_config(key: str, default=None):
    """获取配置项."""
    config = load_config()
    return config.get(key, default)


def set_config(key: str, value):
    """设置配置项."""
    config = load_config()
    config[key] = value
    save_config(config)


def clear_config():
    """清除所有配置."""
    save_config(DEFAULT_CONFIG.copy())
