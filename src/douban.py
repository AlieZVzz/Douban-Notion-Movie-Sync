"""Douban RSS and movie-page parsing."""
from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from datetime import date
from email.utils import parsedate_to_datetime
from typing import Any, Mapping, Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

try:
    from .http_client import create_retry_session
except ImportError:
    from http_client import create_retry_session

logger = logging.getLogger(__name__)

SCORE_MAP = {
    "很差": "⭐",
    "较差": "⭐⭐",
    "还行": "⭐⭐⭐",
    "推荐": "⭐⭐⭐⭐",
    "力荐": "⭐⭐⭐⭐⭐",
}
DEFAULT_SCORE = "⭐⭐⭐"
RE_YEAR = re.compile(r"\((\d{4})\)")
RE_DIRECTOR = re.compile(r"导演:\s*(.+?)(?:,|编剧:|主演:|$)", re.S)
RE_GENRE = re.compile(r"类型:\s*(.+?)(?:,|制片国家|片长:|$)", re.S)
DOUBAN_HOSTS = {"movie.douban.com", "www.douban.com"}


class DoubanParseError(ValueError):
    """Raised when a Douban entry cannot be safely interpreted."""


@dataclass(frozen=True)
class RSSMovie:
    rss_title: str
    cover_url: str
    watched_at: str
    movie_url: str
    score: str
    comment: str


@dataclass(frozen=True)
class MovieDetails:
    title: str
    genres: tuple[str, ...] = ()
    directors: tuple[str, ...] = ()
    year: Optional[int] = None


def compute_sol(challenge: str, difficulty: int = 4, max_nonce: int = 10_000_000) -> int:
    target = "0" * difficulty
    for nonce in range(1, max_nonce + 1):
        digest = hashlib.sha512(f"{challenge}{nonce}".encode("utf-8")).hexdigest()
        if digest.startswith(target):
            return nonce
    raise RuntimeError("Cannot compute Douban challenge solution")


def _safe_douban_url(url: str) -> str:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"} or host not in DOUBAN_HOSTS:
        raise DoubanParseError(f"不支持的豆瓣影片地址: {url}")
    return parsed._replace(scheme="https").geturl()


def split_slash_separated_values(text: str) -> list[str]:
    return [value.strip() for value in text.split("/") if value.strip()]


def remove_year(text: str) -> str:
    return " ".join(RE_YEAR.sub("", text).split()).strip()


def extract_directors(content: BeautifulSoup, info_text: str) -> list[str]:
    links = content.find_all("a", rel="v:directedBy")
    directors = [link.get_text(strip=True) for link in links if link.get_text(strip=True)]
    if directors:
        return directors
    match = RE_DIRECTOR.search(info_text)
    return split_slash_separated_values(match.group(1)) if match else []


def _parse_watched_at(item: Mapping[str, Any]) -> str:
    parsed = item.get("published_parsed")
    if parsed and len(parsed) >= 3:
        return date(int(parsed[0]), int(parsed[1]), int(parsed[2])).isoformat()
    published = str(item.get("published") or "")
    if published:
        try:
            return parsedate_to_datetime(published).date().isoformat()
        except (TypeError, ValueError, OverflowError):
            logger.warning("Unable to parse RSS date %r; using today's date", published)
    return date.today().isoformat()


def parse_rss_item(item: Mapping[str, Any]) -> RSSMovie:
    raw_title = str(item.get("title") or "").strip()
    if "看过" not in raw_title:
        raise DoubanParseError("RSS 条目不是“看过”记录")
    rss_title = raw_title.split("看过", 1)[1].strip()
    movie_url = str(item.get("link") or "").strip()
    if not rss_title or not movie_url:
        raise DoubanParseError("RSS 条目缺少影片名称或链接")
    movie_url = _safe_douban_url(movie_url)

    summary = str(item.get("summary") or "")
    soup = BeautifulSoup(summary, "html.parser")
    image = soup.find("img")
    cover_url = str(image.get("src") or "") if image else ""
    if cover_url:
        cover_url = cover_url.replace("s_ratio_poster", "r")

    text_parts = list(soup.stripped_strings)
    score_text = next((part for part in text_parts if part.strip() in SCORE_MAP), "")
    score = SCORE_MAP.get(score_text.strip(), DEFAULT_SCORE)
    comment = " ".join(
        part.strip()
        for part in text_parts
        if part.strip() and part.strip() not in SCORE_MAP
    )
    return RSSMovie(
        rss_title=rss_title,
        cover_url=cover_url,
        watched_at=_parse_watched_at(item),
        movie_url=movie_url,
        score=score,
        comment=comment,
    )


class DoubanClient:
    def __init__(
        self,
        *,
        timeout: float = 30,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.timeout = timeout
        self.session = session or create_retry_session()
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": "https://www.douban.com/",
        }

    def fetch_page(self, movie_url: str) -> str:
        url = _safe_douban_url(movie_url)
        response = self.session.get(
            url,
            headers=self.headers,
            allow_redirects=False,
            timeout=self.timeout,
        )
        if response.status_code == 200:
            return response.text
        if response.status_code != 302:
            response.raise_for_status()
            raise RuntimeError(f"Unexpected Douban response: {response.status_code}")

        auth_url = urljoin(url, response.headers.get("Location", ""))
        if urlparse(auth_url).hostname != "sec.douban.com":
            raise RuntimeError("Douban returned an unexpected authorization URL")
        auth_response = self.session.get(
            auth_url, headers=self.headers, timeout=self.timeout
        )
        auth_response.raise_for_status()
        form = BeautifulSoup(auth_response.text, "html.parser").find("form", id="sec")
        if not form:
            raise RuntimeError("Douban authorization form not found")

        values = {}
        for field in ("tok", "cha", "red"):
            element = form.find("input", id=field)
            values[field] = str(element.get("value") or "") if element else ""
        if not values["tok"] or not values["cha"]:
            raise RuntimeError("Douban authorization challenge is incomplete")
        values["sol"] = str(compute_sol(values["cha"]))

        challenge = self.session.post(
            "https://sec.douban.com/c",
            data=values,
            headers=self.headers,
            allow_redirects=False,
            timeout=self.timeout,
        )
        if challenge.status_code not in {200, 302}:
            challenge.raise_for_status()
            raise RuntimeError("Douban authorization challenge failed")

        final = self.session.get(url, headers=self.headers, timeout=self.timeout)
        final.raise_for_status()
        return final.text

    def movie_details(self, movie_url: str) -> MovieDetails:
        soup = BeautifulSoup(self.fetch_page(movie_url), "html.parser")
        content = soup.find("div", id="content")
        if not content:
            raise DoubanParseError("豆瓣详情页缺少主体内容")

        structured_title = content.find("span", property="v:itemreviewed")
        h1 = content.find("h1")
        title = (
            structured_title.get_text(" ", strip=True)
            if structured_title
            else h1.get_text(" ", strip=True) if h1 else ""
        )
        if not title:
            raise DoubanParseError("豆瓣详情页缺少影片名称")

        year_element = content.find("span", class_="year")
        year_text = year_element.get_text(strip=True) if year_element else ""
        if year_text and year_text not in title:
            title = f"{title} {year_text}"
        year_match = RE_YEAR.search(title)
        year = int(year_match.group(1)) if year_match else None
        genres = tuple(
            dict.fromkeys(
                element.get_text(strip=True)
                for element in content.find_all("span", property="v:genre")
                if element.get_text(strip=True)
            )
        )
        info = content.find("div", id="info")
        info_text = ",".join(info.stripped_strings) if info else ""
        if not genres:
            genre_match = RE_GENRE.search(info_text)
            genres = tuple(
                split_slash_separated_values(genre_match.group(1))
                if genre_match
                else ()
            )
        directors = tuple(dict.fromkeys(extract_directors(content, info_text)))
        return MovieDetails(title=title, genres=genres, directors=directors, year=year)
