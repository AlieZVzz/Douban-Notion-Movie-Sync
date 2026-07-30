"""Command-line entry point for DoubanNotionSync."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from src.api.notion_api import NotionClient, build_movie_properties
from src.api.tmdb_api import TMDBClient, get_movie_poster
from src.config import Settings, load_settings
from src.douban import (
    DEFAULT_SCORE,
    SCORE_MAP,
    DoubanClient,
    compute_sol,
    extract_directors,
    remove_year,
    split_slash_separated_values,
)
from src.douban import (
    parse_rss_item as parse_rss_movie,
)
from src.http_client import create_retry_session
from src.posters import PosterService, is_usable_poster_url
from src.sync_service import AlreadyRunningError, RunLock, SyncReport, SyncService

LOG_FORMAT = (
    "%(asctime)s - %(name)s - %(levelname)s - "
    "%(funcName)s:%(lineno)d - %(message)s"
)
logger = logging.getLogger("DoubanNotionSync")

__all__ = [
    "DEFAULT_SCORE",
    "MONTH_MAP",
    "SCORE_MAP",
    "build_notion_body",
    "compute_sol",
    "extract_directors",
    "get_configured_image_host_token",
    "is_usable_poster_url",
    "main",
    "parse_rss_item",
    "remove_year",
    "resolve_poster_url",
    "run",
    "split_slash_separated_values",
]

# Retained for callers that imported the old constants.
MONTH_MAP = {
    "Jan": "01",
    "Feb": "02",
    "Mar": "03",
    "Apr": "04",
    "May": "05",
    "Jun": "06",
    "Jul": "07",
    "Aug": "08",
    "Sep": "09",
    "Oct": "10",
    "Nov": "11",
    "Dec": "12",
}


def build_service(settings: Settings) -> SyncService:
    notion_session = create_retry_session(settings.request_retries)
    tmdb_session = create_retry_session(settings.request_retries)
    douban_session = create_retry_session(settings.request_retries)
    rss_session = create_retry_session(settings.request_retries)
    poster_session = create_retry_session(settings.request_retries)
    return SyncService(
        rss_address=settings.rss_address,
        notion=NotionClient(
            settings.notion_api,
            settings.database_id,
            timeout=settings.request_timeout,
            session=notion_session,
            properties=settings.properties,
        ),
        tmdb=TMDBClient(
            settings.tmdb_api_key,
            timeout=settings.request_timeout,
            session=tmdb_session,
        ),
        douban=DoubanClient(
            timeout=settings.request_timeout,
            session=douban_session,
        ),
        posters=PosterService(
            settings.posters_dir,
            image_host_token=settings.image_host_token,
            timeout=settings.request_timeout,
            cleanup=settings.cleanup_posters,
            session=poster_session,
        ),
        rss_session=rss_session,
        timeout=settings.request_timeout,
        item_delay_seconds=settings.item_delay_seconds,
    )


def run(settings: Optional[Settings] = None) -> SyncReport:
    current_settings = settings or load_settings()
    service = build_service(current_settings)
    lock_path = current_settings.posters_dir / ".sync.lock"
    with RunLock(lock_path):
        return service.run()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
    try:
        report = run()
    except AlreadyRunningError as exc:
        logger.warning("%s", exc)
        return 0
    except Exception:
        logger.exception("同步任务发生致命错误")
        return 1

    logger.info(
        "同步完成: 发现=%d 新增=%d 跳过=%d 失败=%d",
        report.discovered,
        report.added,
        report.skipped,
        report.failed,
    )
    return 1 if report.failed else 0


# Compatibility helpers for consumers of the former monolithic module.
def load_config() -> dict[str, Any]:
    settings = load_settings()
    return {
        "notion_api": settings.notion_api,
        "databaseid": settings.database_id,
        "tmdb_api_key": settings.tmdb_api_key,
        "rss_address": settings.rss_address,
        "deepseek_api": settings.deepseek_api,
        "see_api_key": settings.image_host_token,
    }


def parse_rss_item(item: dict[str, Any]) -> tuple[str, str, str, str, str]:
    movie = parse_rss_movie(item)
    return (
        movie.cover_url,
        movie.watched_at,
        movie.movie_url,
        movie.score,
        movie.comment,
    )


def build_notion_body(
    title: str,
    watch_time: str,
    score: str,
    poster_url: str,
    comment: str,
    movie_url: str,
    movie_types: list[str],
    directors: list[str],
) -> dict[str, Any]:
    return build_movie_properties(
        title=title,
        watch_time=watch_time,
        score=score,
        poster_url=poster_url,
        comment=comment,
        movie_url=movie_url,
        movie_types=movie_types,
        directors=directors,
    )


def get_configured_image_host_token(config: dict[str, Any]) -> Optional[str]:
    value = str(config.get("see_api_key") or config.get("smms_token") or "").strip()
    return (
        None
        if not value or value.startswith("your_") or value.startswith("secret_your_")
        else value
    )


def upload_douban_cover_to_image_host(
    cover_url: str,
    movie_name: str,
    image_host_token: Optional[str],
) -> Optional[str]:
    del movie_name
    return PosterService(
        Path("posters"), image_host_token=image_host_token
    ).rehost(cover_url)


def resolve_poster_url(
    config: dict[str, Any],
    movie_name: str,
    movie_id: Optional[int],
    cover_url: str,
) -> str:
    if movie_id:
        poster = get_movie_poster(str(config["tmdb_api_key"]), movie_id)
        if is_usable_poster_url(poster):
            return str(poster)
    return (
        upload_douban_cover_to_image_host(
            cover_url,
            movie_name,
            get_configured_image_host_token(config),
        )
        or ""
    )


if __name__ == "__main__":
    raise SystemExit(main())
