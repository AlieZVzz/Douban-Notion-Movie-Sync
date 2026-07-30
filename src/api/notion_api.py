"""Small, reliable client for the Notion API."""
from __future__ import annotations

import logging
from typing import Any, Iterable, Optional

import requests

try:
    from ..config import NotionProperties, load_settings
    from ..http_client import create_retry_session
except ImportError:  # Support ``python src/main.py`` during migration.
    from config import NotionProperties, load_settings
    from http_client import create_retry_session

logger = logging.getLogger(__name__)

NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


class NotionClient:
    def __init__(
        self,
        token: str,
        database_id: str,
        *,
        timeout: float = 30,
        session: Optional[requests.Session] = None,
        properties: Optional[NotionProperties] = None,
    ) -> None:
        self.database_id = database_id
        self.timeout = timeout
        self.session = session or create_retry_session()
        self.properties = properties or NotionProperties()
        self.headers = {
            "Accept": "application/json",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token.removeprefix('Bearer ').strip()}",
        }

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        response = self.session.request(
            method,
            f"{NOTION_API_BASE}{path}",
            headers=self.headers,
            timeout=self.timeout,
            **kwargs,
        )
        try:
            response.raise_for_status()
        except requests.HTTPError:
            logger.error(
                "Notion request failed: %s %s status=%s body=%s",
                method,
                path,
                response.status_code,
                response.text[:500],
            )
            raise
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError("Notion API returned a non-object JSON response")
        return data

    def query_database(self) -> list[dict[str, Any]]:
        """Read all database pages using Notion's documented cursor fields."""
        results: list[dict[str, Any]] = []
        cursor: Optional[str] = None
        while True:
            payload = {"page_size": 100}
            if cursor:
                payload["start_cursor"] = cursor
            page = self._request(
                "POST", f"/databases/{self.database_id}/query", json=payload
            )
            page_results = page.get("results", [])
            if not isinstance(page_results, list):
                raise ValueError("Notion database response has invalid results")
            results.extend(item for item in page_results if isinstance(item, dict))
            if not page.get("has_more"):
                return results
            cursor = page.get("next_cursor")
            if not cursor:
                raise ValueError("Notion response has_more=true but next_cursor is empty")

    def existing_movie_urls(self) -> set[str]:
        urls: set[str] = set()
        property_name = self.properties.movie_url
        for page in self.query_database():
            value = page.get("properties", {}).get(property_name, {})
            movie_url = value.get("url") if isinstance(value, dict) else None
            if isinstance(movie_url, str) and movie_url:
                urls.add(movie_url)
        return urls

    def create_movie(self, properties: dict[str, Any]) -> dict[str, Any]:
        """Create a page and return the confirmed Notion response."""
        response = self._request(
            "POST",
            "/pages",
            json={
                "parent": {
                    "type": "database_id",
                    "database_id": self.database_id,
                },
                **properties,
            },
        )
        if not response.get("id"):
            raise ValueError("Notion create-page response did not include a page id")
        return response

    def archive_page(self, page_id: str) -> dict[str, Any]:
        return self._request("PATCH", f"/pages/{page_id}", json={"archived": True})


def build_movie_properties(
    *,
    title: str,
    watch_time: str,
    score: str,
    poster_url: str,
    comment: str,
    movie_url: str,
    movie_types: Iterable[str],
    directors: Iterable[str],
    names: Optional[NotionProperties] = None,
) -> dict[str, Any]:
    """Build a Notion create-page properties payload."""
    fields = names or NotionProperties()
    properties: dict[str, Any] = {
        fields.title: {
            "title": [{"type": "text", "text": {"content": title[:2000]}}]
        },
        fields.watched_at: {"date": {"start": watch_time}},
        fields.score: {"type": "select", "select": {"name": score}},
        fields.comment: {
            "type": "rich_text",
            "rich_text": [
                {
                    "type": "text",
                    "text": {"content": comment[:2000]},
                    "plain_text": comment[:2000],
                }
            ],
        },
        fields.movie_url: {"type": "url", "url": movie_url},
        fields.genres: {
            "type": "multi_select",
            "multi_select": [{"name": value[:100]} for value in movie_types if value],
        },
        fields.directors: {
            "type": "multi_select",
            "multi_select": [{"name": value[:100]} for value in directors if value],
        },
    }
    if poster_url:
        properties[fields.poster] = {
            "files": [
                {
                    "type": "external",
                    "name": "封面",
                    "external": {"url": poster_url},
                }
            ]
        }
    return {"properties": properties}


# Backward-compatible helpers for existing callers. Configuration is loaded lazily.
def _default_client(database_id: Optional[str] = None) -> NotionClient:
    settings = load_settings()
    return NotionClient(
        settings.notion_api,
        database_id or settings.database_id,
        timeout=settings.request_timeout,
        properties=settings.properties,
    )


def DataBase_item_query(query_database_id: str) -> list[dict[str, Any]]:
    return _default_client(query_database_id).query_database()


def DataBase_additem(
    database_id: str, body_properties: dict[str, Any], station: str = ""
) -> dict[str, Any]:
    result = _default_client(database_id).create_movie(body_properties)
    logger.info("%s·更新成功", station)
    return result


def select_items_form_Databaseitems(
    items: Iterable[dict[str, Any]], label: str, value: Any
) -> list[dict[str, Any]]:
    selected = []
    for item in items:
        property_value = item.get("properties", {}).get(label, {})
        property_type = property_value.get("type")
        candidate = property_value.get(property_type) if property_type else None
        if candidate == value:
            selected.append(item)
    return selected
