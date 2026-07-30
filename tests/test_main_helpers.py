import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from unittest.mock import patch

from bs4 import BeautifulSoup

from src.main import (
    DEFAULT_SCORE,
    MONTH_MAP,
    SCORE_MAP,
    build_notion_body,
    extract_directors,
    get_configured_image_host_token,
    is_usable_poster_url,
    parse_rss_item,
    remove_year,
    resolve_poster_url,
)


def test_remove_year():
    """Test removing year from movie title"""
    assert remove_year("Inception (2010)") == "Inception"
    assert remove_year("The Matrix (1999) (4K Remaster)") == "The Matrix (4K Remaster)"
    assert remove_year("No Year Here") == "No Year Here"
    assert remove_year("") == ""


def test_parse_rss_item_basic():
    """Test basic RSS item parsing"""
    mock_item = {
        "title": "看过 Inception",
        "summary": '<img src="https://example.com/poster.jpg"> <p>力荐</p>',
        "published": "Mon, 01 Jan 2023 00:00:00 GMT",
        "link": "https://movie.douban.com/subject/123456/",
    }

    cover_url, watch_time, movie_url, score, comment = parse_rss_item(mock_item)

    assert cover_url == "https://example.com/poster.jpg"
    assert watch_time == "2023-01-01"
    assert movie_url == "https://movie.douban.com/subject/123456/"
    assert score == "⭐⭐⭐⭐⭐"
    assert comment == ""


def test_parse_rss_item_no_poster():
    """Test RSS item parsing when no poster is available"""
    mock_item = {
        "title": "看过 The Matrix",
        "summary": "<p>推荐</p>",
        "published": "Tue, 15 Feb 2023 00:00:00 GMT",
        "link": "https://movie.douban.com/subject/789012/",
    }

    cover_url, watch_time, movie_url, score, comment = parse_rss_item(mock_item)

    assert cover_url == ""
    assert watch_time == "2023-02-15"
    assert movie_url == "https://movie.douban.com/subject/789012/"
    assert score == "⭐⭐⭐⭐"


def test_parse_rss_item_no_score():
    """Test RSS item parsing when no score is available"""
    mock_item = {
        "title": "看过 Interstellar",
        "summary": "Some random summary without score",
        "published": "Wed, 20 Mar 2023 00:00:00 GMT",
        "link": "https://movie.douban.com/subject/345678/",
    }

    cover_url, watch_time, movie_url, score, comment = parse_rss_item(mock_item)

    assert score == DEFAULT_SCORE


def test_build_notion_body_with_poster():
    """Test building Notion body with poster URL"""
    body = build_notion_body(
        title="Inception",
        watch_time="2023-01-01",
        score="⭐⭐⭐⭐⭐",
        poster_url="https://example.com/poster.jpg",
        comment="Great movie!",
        movie_url="https://movie.douban.com/subject/123456/",
        movie_types=["Sci-Fi", "Action"],
        directors=["Christopher Nolan"],
    )

    expected_properties = {
        "名称": {"title": [{"type": "text", "text": {"content": "Inception"}}]},
        "观看时间": {"date": {"start": "2023-01-01"}},
        "评分": {"type": "select", "select": {"name": "⭐⭐⭐⭐⭐"}},
        "有啥想说的不": {
            "type": "rich_text",
            "rich_text": [
                {"type": "text", "text": {"content": "Great movie!"}, "plain_text": "Great movie!"}
            ],
        },
        "影片链接": {"type": "url", "url": "https://movie.douban.com/subject/123456/"},
        "类型": {"type": "multi_select", "multi_select": [{"name": "Sci-Fi"}, {"name": "Action"}]},
        "导演": {"type": "multi_select", "multi_select": [{"name": "Christopher Nolan"}]},
        "封面": {
            "files": [
                {
                    "type": "external",
                    "name": "封面",
                    "external": {"url": "https://example.com/poster.jpg"},
                }
            ]
        },
    }

    assert body["properties"] == expected_properties


def test_build_notion_body_without_poster():
    """Test building Notion body without poster URL"""
    body = build_notion_body(
        title="The Matrix",
        watch_time="2023-02-15",
        score="⭐⭐⭐⭐",
        poster_url="",
        comment="Classic!",
        movie_url="https://movie.douban.com/subject/789012/",
        movie_types=["Sci-Fi", "Action"],
        directors=["Lana Wachowski", "Lilly Wachowski"],
    )

    # Should not have '封面' property when poster_url is empty
    assert "封面" not in body["properties"]
    assert body["properties"]["名称"]["title"][0]["text"]["content"] == "The Matrix"
    assert len(body["properties"]["导演"]["multi_select"]) == 2


def test_extract_directors_keeps_full_english_names_from_structured_links():
    """Test director extraction from Douban structured director links"""
    soup = BeautifulSoup(
        """
        <div id="content">
            <div id="info">
                导演: <a rel="v:directedBy">Christopher Nolan</a> /
                <a rel="v:directedBy">Jonathan Nolan</a>
            </div>
        </div>
        """,
        "html.parser",
    )

    assert extract_directors(soup, "") == ["Christopher Nolan", "Jonathan Nolan"]


def test_extract_directors_fallback_keeps_english_last_name():
    """Test fallback director parsing keeps full English names"""
    soup = BeautifulSoup("<div id='content'></div>", "html.parser")
    info_text = "导演: Sam Mendes / Christopher Nolan,编剧: Someone"

    assert extract_directors(soup, info_text) == ["Sam Mendes", "Christopher Nolan"]


def test_is_usable_poster_url_rejects_tmdb_placeholder():
    """Test that TMDB placeholder text is not treated as a usable URL"""
    assert is_usable_poster_url("https://image.tmdb.org/t/p/w500/poster.jpg") is True
    assert is_usable_poster_url("No poster available") is False
    assert is_usable_poster_url("") is False
    assert is_usable_poster_url(None) is False


def test_get_configured_image_host_token_filters_placeholder():
    """Test S.EE API key config parsing"""
    assert get_configured_image_host_token({"see_api_key": "abc123"}) == "abc123"
    assert get_configured_image_host_token({"smms_token": "legacy-token"}) == "legacy-token"
    assert get_configured_image_host_token({"see_api_key": "your_see_api_key_here"}) is None
    assert get_configured_image_host_token({"smms_token": "your_smms_token_here"}) is None
    assert get_configured_image_host_token({}) is None


@patch("src.main.upload_douban_cover_to_image_host")
@patch("src.main.get_movie_poster")
def test_resolve_poster_url_uploads_douban_cover_when_tmdb_missing(mock_get_poster, mock_upload):
    """Test Douban covers are rehosted instead of being written directly to Notion"""
    mock_get_poster.return_value = "No poster available"
    mock_upload.return_value = "https://s2.loli.net/poster.jpg"

    result = resolve_poster_url(
        {"tmdb_api_key": "fake_tmdb_key", "see_api_key": "fake_see_api_key"},
        "Inception",
        12345,
        "https://img.doubanio.com/view/photo/s_ratio_poster/public/p123.jpg",
    )

    assert result == "https://s2.loli.net/poster.jpg"
    mock_upload.assert_called_once_with(
        "https://img.doubanio.com/view/photo/s_ratio_poster/public/p123.jpg",
        "Inception",
        "fake_see_api_key",
    )


@patch("src.main.upload_douban_cover_to_image_host")
@patch("src.main.get_movie_poster")
def test_resolve_poster_url_does_not_fallback_to_douban_url_without_token(
    mock_get_poster, mock_upload
):
    """Test original Douban URLs are not written to Notion when rehosting is unavailable"""
    mock_get_poster.return_value = "No poster available"
    mock_upload.return_value = None

    result = resolve_poster_url(
        {"tmdb_api_key": "fake_tmdb_key"},
        "Inception",
        12345,
        "https://img.doubanio.com/view/photo/s_ratio_poster/public/p123.jpg",
    )

    assert result == ""


def test_month_map_completeness():
    """Test that MONTH_MAP covers all months"""
    expected_months = [
        "Jan",
        "Feb",
        "Mar",
        "Apr",
        "May",
        "Jun",
        "Jul",
        "Aug",
        "Sep",
        "Oct",
        "Nov",
        "Dec",
    ]
    assert list(MONTH_MAP.keys()) == expected_months
    assert all(len(val) == 2 and val.isdigit() for val in MONTH_MAP.values())


def test_score_map_completeness():
    """Test that SCORE_MAP covers all expected scores"""
    expected_scores = ["很差", "较差", "还行", "推荐", "力荐"]
    assert list(SCORE_MAP.keys()) == expected_scores
    assert all("⭐" in val for val in SCORE_MAP.values())
