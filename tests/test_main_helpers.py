import sys
import os
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest
from unittest.mock import Mock, patch, MagicMock
from src.main import (
    remove_year, parse_rss_item, build_notion_body, 
    MONTH_MAP, SCORE_MAP, DEFAULT_SCORE
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
        "link": "https://movie.douban.com/subject/123456/"
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
        "link": "https://movie.douban.com/subject/789012/"
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
        "link": "https://movie.douban.com/subject/345678/"
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
        directors=["Christopher Nolan"]
    )
    
    expected_properties = {
        '名称': {'title': [{'type': 'text', 'text': {'content': 'Inception'}}]},
        '观看时间': {'date': {'start': '2023-01-01'}},
        '评分': {'type': 'select', 'select': {'name': '⭐⭐⭐⭐⭐'}},
        '有啥想说的不': {'type': 'rich_text', 'rich_text': [{'type': 'text', 'text': {'content': 'Great movie!'}, 'plain_text': 'Great movie!'}]},
        '影片链接': {'type': 'url', 'url': 'https://movie.douban.com/subject/123456/'},
        '类型': {'type': 'multi_select', 'multi_select': [{'name': 'Sci-Fi'}, {'name': 'Action'}]},
        '导演': {'type': 'multi_select', 'multi_select': [{'name': 'Christopher Nolan'}]},
        '封面': {'files': [{'type': 'external', 'name': '封面', 'external': {'url': 'https://example.com/poster.jpg'}}]}
    }
    
    assert body['properties'] == expected_properties


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
        directors=["Lana Wachowski", "Lilly Wachowski"]
    )
    
    # Should not have '封面' property when poster_url is empty
    assert '封面' not in body['properties']
    assert body['properties']['名称']['title'][0]['text']['content'] == "The Matrix"
    assert len(body['properties']['导演']['multi_select']) == 2


def test_month_map_completeness():
    """Test that MONTH_MAP covers all months"""
    expected_months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                      'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    assert list(MONTH_MAP.keys()) == expected_months
    assert all(len(val) == 2 and val.isdigit() for val in MONTH_MAP.values())


def test_score_map_completeness():
    """Test that SCORE_MAP covers all expected scores"""
    expected_scores = ['很差', '较差', '还行', '推荐', '力荐']
    assert list(SCORE_MAP.keys()) == expected_scores
    assert all('⭐' in val for val in SCORE_MAP.values())