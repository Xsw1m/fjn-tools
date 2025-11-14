import json
import os
from pathlib import Path

# 项目根目录下的 config/config.json（真实配置文件，建议被 .gitignore 忽略）
CONFIG_PATH = Path(__file__).resolve().parent.parent / 'config' / 'config.json'

_CACHE = None

def load_config() -> dict:
    """
    加载项目配置。优先读取 `config/config.json`，读取失败则返回空字典。

    返回值示例：
    {
      "SLT_SUMMARY_ROOT": "//server/SLT_Summary",
      "MAPPING_ROOT": "//server/3270"
    }
    """
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            _CACHE = json.load(f) or {}
    except Exception:
        _CACHE = {}
    return _CACHE

def get_config(key: str, default: str | None = None) -> str | None:
    """
    获取配置项：先读 `config/config.json`，若为空则回退到同名环境变量，最后使用 default。

    参数：
    - key: 配置键，如 "SLT_SUMMARY_ROOT"、"MAPPING_ROOT"
    - default: 默认值（可选）

    返回：字符串或 None
    """
    cfg = load_config()
    val = cfg.get(key)
    if val is None or str(val).strip() == '':
        env = os.environ.get(key)
        if env is not None and str(env).strip() != '':
            return env.strip()
        return default
    return str(val).strip()