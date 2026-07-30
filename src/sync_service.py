"""Application-level orchestration for synchronizing Douban movies to Notion."""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

import feedparser
import requests

from .api.notion_api import NotionClient, build_movie_properties
from .api.tmdb_api import TMDBClient
from .douban import (
    DoubanClient,
    DoubanParseError,
    MovieDetails,
    parse_rss_item,
    remove_year,
)
from .posters import PosterService, is_usable_poster_url

logger = logging.getLogger(__name__)


class FeedError(RuntimeError):
    """Raised when the RSS feed cannot be fetched or parsed safely."""


class AlreadyRunningError(RuntimeError):
    """Raised when another synchronization process owns the run lock."""


@dataclass
class SyncReport:
    discovered: int = 0
    added: int = 0
    skipped: int = 0
    failed: int = 0
    failures: list[str] = field(default_factory=list)


class RunLock:
    """Non-blocking file lock to prevent overlapping cron runs."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._file: Any = None

    def __enter__(self) -> "RunLock":
        import fcntl

        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._file = self.path.open("w")
        try:
            fcntl.flock(self._file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            self._file.close()
            raise AlreadyRunningError("另一个同步任务仍在运行") from exc
        self._file.write(str(os.getpid()))
        self._file.flush()
        return self

    def __exit__(self, *_: Any) -> None:
        if self._file:
            import fcntl

            fcntl.flock(self._file.fileno(), fcntl.LOCK_UN)
            self._file.close()


class SyncService:
    def __init__(
        self,
        *,
        rss_address: str,
        notion: NotionClient,
        tmdb: TMDBClient,
        douban: DoubanClient,
        posters: PosterService,
        rss_session: requests.Session,
        timeout: float = 30,
        item_delay_seconds: float = 3,
    ) -> None:
        self.rss_address = rss_address
        self.notion = notion
        self.tmdb = tmdb
        self.douban = douban
        self.posters = posters
        self.rss_session = rss_session
        self.timeout = timeout
        self.item_delay_seconds = item_delay_seconds

    def fetch_entries(self) -> list[Mapping[str, Any]]:
        response = self.rss_session.get(
            self.rss_address,
            headers={"User-Agent": self.douban.headers["User-Agent"]},
            timeout=self.timeout,
        )
        response.raise_for_status()
        feed = feedparser.parse(response.content)
        entries = feed.get("entries", [])
        if getattr(feed, "bozo", False) and not entries:
            raise FeedError(f"豆瓣 RSS 解析失败: {getattr(feed, 'bozo_exception', '')}")
        if not entries:
            raise FeedError("豆瓣 RSS 没有返回任何条目")
        return [entry for entry in entries if isinstance(entry, Mapping)]

    def _details_with_fallback(self, movie_url: str, rss_title: str) -> MovieDetails:
        try:
            return self.douban.movie_details(movie_url)
        except (DoubanParseError, requests.RequestException, RuntimeError) as exc:
            logger.warning(
                "Douban detail lookup failed for %s; using RSS title: %s",
                movie_url,
                exc,
            )
            return MovieDetails(title=rss_title)

    def _poster_url(
        self, details: MovieDetails, cover_url: str
    ) -> str:
        movie_name = remove_year(details.title)
        try:
            movie_id = self.tmdb.search_movie(movie_name, details.year)
            if movie_id:
                poster_url = self.tmdb.poster_url(movie_id)
                if is_usable_poster_url(poster_url):
                    return str(poster_url)
        except (requests.RequestException, ValueError) as exc:
            logger.warning("TMDB poster lookup failed for %s: %s", movie_name, exc)
        return self.posters.rehost(cover_url) or ""

    def sync_entries(
        self,
        entries: Iterable[Mapping[str, Any]],
        *,
        existing_urls: Optional[set[str]] = None,
    ) -> SyncReport:
        report = SyncReport()
        watched_urls = (
            set(existing_urls)
            if existing_urls is not None
            else self.notion.existing_movie_urls()
        )

        for entry in entries:
            title = str(entry.get("title") or "")
            if "看过" not in title:
                continue
            report.discovered += 1
            try:
                movie = parse_rss_item(entry)
                if movie.movie_url in watched_urls:
                    report.skipped += 1
                    continue

                details = self._details_with_fallback(movie.movie_url, movie.rss_title)
                if not details.title.strip():
                    raise DoubanParseError("影片名称为空，拒绝写入 Notion")
                poster_url = self._poster_url(details, movie.cover_url)
                payload = build_movie_properties(
                    title=details.title,
                    watch_time=movie.watched_at,
                    score=movie.score,
                    poster_url=poster_url,
                    comment=movie.comment,
                    movie_url=movie.movie_url,
                    movie_types=details.genres,
                    directors=details.directors,
                    names=self.notion.properties,
                )
                self.notion.create_movie(payload)
                watched_urls.add(movie.movie_url)
                report.added += 1
                if self.item_delay_seconds:
                    time.sleep(self.item_delay_seconds)
            except (
                DoubanParseError,
                requests.RequestException,
                RuntimeError,
                ValueError,
            ) as exc:
                report.failed += 1
                message = f"{title or '<untitled>'}: {exc}"
                report.failures.append(message)
                logger.exception("Movie synchronization failed: %s", message)
        return report

    def run(self) -> SyncReport:
        return self.sync_entries(self.fetch_entries())
