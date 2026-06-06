"""Configuration loader. Reads ~/.songos/config.yaml."""
import os
import yaml

DEFAULT_CONFIG = {
    "vault_path": os.path.expanduser("~/Desktop/obsidian知识库/我的数字花园"),
    "db_path": os.path.expanduser("~/.songos/songos.db"),
    "user_name": "",          # Empty = auto-detect from OS username
    "output_language": "zh",  # "zh" or "en"
}

CONFIG_DIR = os.path.expanduser("~/.songos")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.yaml")


def load_config() -> dict:
    """Load config from ~/.songos/config.yaml, merge with defaults."""
    config = dict(DEFAULT_CONFIG)
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            user_config = yaml.safe_load(f) or {}
            config.update(user_config)
    return config


def ensure_config_dir():
    """Create ~/.songos/ if it doesn't exist."""
    os.makedirs(CONFIG_DIR, exist_ok=True)


def get_vault_path() -> str:
    return load_config()["vault_path"]


def get_db_path() -> str:
    return load_config()["db_path"]


def get_user_name() -> str:
    """Return configured user name, fallback to OS username."""
    name = load_config().get("user_name", "")
    if name:
        return name
    return os.environ.get("USER", os.environ.get("USERNAME", ""))
