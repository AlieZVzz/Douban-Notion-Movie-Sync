"""Application configuration loading and validation."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional

import yaml


class ConfigurationError(ValueError):
    """Raised when required application configuration is missing or invalid."""


@dataclass(frozen=True)
class NotionProperties:
    title: str = "名称"
    watched_at: str = "观看时间"
    score: str = "评分"
    comment: str = "有啥想说的不"
    movie_url: str = "影片链接"
    genres: str = "类型"
    directors: str = "导演"
    poster: str = "封面"


@dataclass(frozen=True)
class Settings:
    notion_api: str
    database_id: str
    tmdb_api_key: str
    rss_address: str
    deepseek_api: Optional[str] = None
    image_host_token: Optional[str] = None
    request_timeout: float = 30.0
    request_retries: int = 3
    item_delay_seconds: float = 3.0
    posters_dir: Path = Path("posters")
    cleanup_posters: bool = True
    properties: NotionProperties = field(default_factory=NotionProperties)


_PLACEHOLDERS = {
    "",
    "secret_your_notion_api_key_here",
    "your_database_id_here",
    "your_tmdb_api_key_here",
    "your_deepseek_api_key_here",
    "your_see_api_key_here",
    "your_smms_token_here",
}


def _optional_secret(value: Any) -> Optional[str]:
    normalized = str(value or "").strip()
    return None if normalized.lower() in _PLACEHOLDERS else normalized


def _required(config: Mapping[str, Any], key: str) -> str:
    value = str(config.get(key) or "").strip()
    if value.lower() in _PLACEHOLDERS or "your_user_id" in value:
        raise ConfigurationError(f"配置项 {key!r} 未填写或仍是示例值")
    return value


def _env_or_config(config: Mapping[str, Any], env_name: str, key: str) -> Any:
    return os.getenv(env_name, config.get(key))


def load_settings(config_path: Optional[Path] = None) -> Settings:
    """Load settings from YAML, allowing secrets and core fields to use env overrides."""
    path = config_path or Path(
        os.getenv("DOUBAN_NOTION_CONFIG", Path(__file__).with_name("config.yaml"))
    )
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except FileNotFoundError as exc:
        raise ConfigurationError(
            f"找不到配置文件 {path}，请复制 config.example.yaml 并填写必要配置"
        ) from exc
    except yaml.YAMLError as exc:
        raise ConfigurationError(f"配置文件 {path} 不是有效的 YAML") from exc

    if not isinstance(raw, dict):
        raise ConfigurationError("配置文件顶层必须是键值映射")

    merged = dict(raw)
    mappings = {
        "notion_api": "NOTION_API_TOKEN",
        "databaseid": "NOTION_DATABASE_ID",
        "tmdb_api_key": "TMDB_API_KEY",
        "rss_address": "DOUBAN_RSS_ADDRESS",
        "deepseek_api": "DEEPSEEK_API_KEY",
        "see_api_key": "SEE_API_KEY",
    }
    for key, env_name in mappings.items():
        merged[key] = _env_or_config(raw, env_name, key)

    property_values = raw.get("notion_properties") or {}
    if not isinstance(property_values, dict):
        raise ConfigurationError("notion_properties 必须是键值映射")

    properties = NotionProperties(
        **{
            key: str(value)
            for key, value in property_values.items()
            if key in NotionProperties.__dataclass_fields__
        }
    )
    posters_dir = Path(
        os.getenv("POSTERS_DIR", str(raw.get("posters_dir") or "posters"))
    )

    return Settings(
        notion_api=_required(merged, "notion_api"),
        database_id=_required(merged, "databaseid"),
        tmdb_api_key=_required(merged, "tmdb_api_key"),
        rss_address=_required(merged, "rss_address"),
        deepseek_api=_optional_secret(merged.get("deepseek_api")),
        image_host_token=_optional_secret(
            merged.get("see_api_key") or merged.get("smms_token")
        ),
        request_timeout=float(raw.get("request_timeout", 30)),
        request_retries=int(raw.get("request_retries", 3)),
        item_delay_seconds=float(raw.get("item_delay_seconds", 3)),
        posters_dir=posters_dir,
        cleanup_posters=bool(raw.get("cleanup_posters", True)),
        properties=properties,
    )

