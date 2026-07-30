from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

import requests

from src.api.notion_api import NotionClient
from src.api.tmdb_api import TMDBClient
from src.config import ConfigurationError, load_settings
from src.douban import DoubanClient, MovieDetails, parse_rss_item
from src.sync_service import AlreadyRunningError, RunLock, SyncService


class FakeResponse:
    def __init__(self, payload, status_code=200, text=""):
        self._payload = payload
        self.status_code = status_code
        self.text = text
        self.content = text.encode()
        self.headers = {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"status={self.status_code}", response=self)


class NotionClientTests(unittest.TestCase):
    def test_pagination_uses_next_cursor_until_has_more_is_false(self):
        session = Mock()
        session.request.side_effect = [
            FakeResponse(
                {"results": [{"id": "a"}], "has_more": True, "next_cursor": "next"}
            ),
            FakeResponse(
                {"results": [{"id": "b"}], "has_more": False, "next_cursor": None}
            ),
        ]
        client = NotionClient("secret", "database", session=session)

        self.assertEqual([item["id"] for item in client.query_database()], ["a", "b"])
        self.assertEqual(
            session.request.call_args_list[1].kwargs["json"]["start_cursor"], "next"
        )

    def test_create_movie_requires_confirmed_page_id(self):
        session = Mock()
        session.request.return_value = FakeResponse({"object": "page"})
        client = NotionClient("secret", "database", session=session)

        with self.assertRaisesRegex(ValueError, "page id"):
            client.create_movie({"properties": {}})


class DoubanParsingTests(unittest.TestCase):
    def test_rss_parser_uses_structured_date_and_extracts_comment(self):
        movie = parse_rss_item(
            {
                "title": "看过 盗梦空间",
                "summary": '<img src="https://img.example/p.jpg"><p>力荐</p><p>值得重看</p>',
                "published_parsed": (2024, 2, 3, 0, 0, 0, 0, 0, 0),
                "link": "http://movie.douban.com/subject/3541415/",
            }
        )

        self.assertEqual(movie.watched_at, "2024-02-03")
        self.assertEqual(movie.score, "⭐⭐⭐⭐⭐")
        self.assertEqual(movie.comment, "值得重看")
        self.assertTrue(movie.movie_url.startswith("https://"))

    def test_movie_details_prefers_structured_fields(self):
        client = DoubanClient(session=Mock())
        client.fetch_page = Mock(
            return_value="""
            <div id="content">
              <h1><span property="v:itemreviewed">Inception (2010)</span></h1>
              <div id="info">
                <a rel="v:directedBy">Christopher Nolan</a>
                <span property="v:genre">剧情</span>
                <span property="v:genre">科幻</span>
              </div>
            </div>
            """
        )

        details = client.movie_details("https://movie.douban.com/subject/3541415/")
        self.assertEqual(details.title, "Inception (2010)")
        self.assertEqual(details.year, 2010)
        self.assertEqual(details.genres, ("剧情", "科幻"))
        self.assertEqual(details.directors, ("Christopher Nolan",))

    def test_movie_details_keeps_separate_douban_year(self):
        client = DoubanClient(session=Mock())
        client.fetch_page = Mock(
            return_value="""
            <div id="content">
              <h1>
                <span property="v:itemreviewed">盗梦空间</span>
                <span class="year">(2010)</span>
              </h1>
              <div id="info"></div>
            </div>
            """
        )

        details = client.movie_details("https://movie.douban.com/subject/3541415/")
        self.assertEqual(details.title, "盗梦空间 (2010)")
        self.assertEqual(details.year, 2010)


class SyncServiceTests(unittest.TestCase):
    @staticmethod
    def service(notion):
        tmdb = Mock(spec=TMDBClient)
        tmdb.search_movie.return_value = None
        douban = Mock(spec=DoubanClient)
        douban.headers = {"User-Agent": "test"}
        douban.movie_details.return_value = MovieDetails("Inception (2010)")
        posters = Mock()
        posters.rehost.return_value = None
        return SyncService(
            rss_address="https://example.test/rss",
            notion=notion,
            tmdb=tmdb,
            douban=douban,
            posters=posters,
            rss_session=Mock(),
            item_delay_seconds=0,
        )

    def test_duplicate_entries_are_only_created_once_per_run(self):
        notion = Mock(spec=NotionClient)
        notion.properties = NotionClient("x", "y").properties
        notion.create_movie.return_value = {"id": "page"}
        entry = {
            "title": "看过 Inception",
            "summary": "<p>推荐</p>",
            "published_parsed": (2024, 1, 2, 0, 0, 0, 0, 0, 0),
            "link": "https://movie.douban.com/subject/3541415/",
        }

        report = self.service(notion).sync_entries([entry, entry], existing_urls=set())

        self.assertEqual(report.added, 1)
        self.assertEqual(report.skipped, 1)
        notion.create_movie.assert_called_once()

    def test_failed_notion_write_is_not_counted_as_added(self):
        notion = Mock(spec=NotionClient)
        notion.properties = NotionClient("x", "y").properties
        notion.create_movie.side_effect = requests.HTTPError("Notion unavailable")
        entry = {
            "title": "看过 Inception",
            "summary": "<p>推荐</p>",
            "published_parsed": (2024, 1, 2, 0, 0, 0, 0, 0, 0),
            "link": "https://movie.douban.com/subject/3541415/",
        }

        report = self.service(notion).sync_entries([entry], existing_urls=set())

        self.assertEqual(report.added, 0)
        self.assertEqual(report.failed, 1)


class ConfigurationTests(unittest.TestCase):
    def test_placeholder_values_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.yaml"
            path.write_text(
                "notion_api: secret_your_notion_api_key_here\n"
                "databaseid: db\n"
                "tmdb_api_key: tmdb\n"
                "rss_address: https://www.douban.com/feed/people/1/interests\n",
                encoding="utf-8",
            )
            with self.assertRaises(ConfigurationError):
                load_settings(path)


class RunLockTests(unittest.TestCase):
    def test_second_run_cannot_acquire_same_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".sync.lock"
            with RunLock(path):
                with self.assertRaises(AlreadyRunningError):
                    with RunLock(path):
                        self.fail("second lock unexpectedly acquired")


if __name__ == "__main__":
    unittest.main()
