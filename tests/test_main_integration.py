import sys
import os
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest
from unittest.mock import Mock, patch, MagicMock
from src.main import process_movie_entry, load_config


@pytest.fixture
def mock_config():
    """Mock configuration for testing"""
    return {
        "tmdb_api_key": "fake_tmdb_key",
        "databaseid": "fake_database_id",
        "rss_address": "fake_rss_url"
    }


@pytest.fixture
def mock_rss_item():
    """Mock RSS item for testing"""
    return {
        "title": "看过 Inception",
        "summary": '<img src="https://example.com/poster.jpg"> <p>力荐</p>',
        "published": "Mon, 01 Jan 2023 00:00:00 GMT",
        "link": "https://movie.douban.com/subject/123456/"
    }


@patch('src.main.select_items_form_Databaseitems')
@patch('src.main.DataBase_additem')
@patch('src.main.get_movie_poster')
@patch('src.main.search_movie')
@patch('src.main.fetch_movie_details')
def test_process_movie_entry_new_movie(
    mock_fetch_details, mock_search, mock_get_poster, 
    mock_additem, mock_select, mock_rss_item, mock_config
):
    """Test processing a new movie entry"""
    # Setup mocks
    mock_select.return_value = []  # Movie not in database
    mock_fetch_details.return_value = ("Inception (2010)", ["Sci-Fi"], ["Christopher Nolan"])
    mock_search.return_value = 12345
    mock_get_poster.return_value = "https://tmdb.org/poster.jpg"
    
    request_headers = {'User-Agent': 'test'}
    notion_movies = []
    watched_urls = set()
    
    result = process_movie_entry(
        mock_rss_item, watched_urls, mock_config, 
        request_headers, notion_movies
    )
    
    assert result is True
    # Note: We can't easily test DataBase_additem call due to complex body structure
    # But we can verify other calls
    mock_search.assert_called_once_with("fake_tmdb_key", "Inception")
    mock_get_poster.assert_called_once_with("fake_tmdb_key", 12345)


@patch('src.main.select_items_form_Databaseitems')
def test_process_movie_entry_existing_movie(mock_select, mock_rss_item, mock_config):
    """Test processing an existing movie entry (should skip)"""
    mock_select.return_value = [{"id": "fake_id"}]  # Movie already exists
    
    request_headers = {'User-Agent': 'test'}
    notion_movies = [{"id": "fake_id"}]  # Simplified structure
    watched_urls = set()
    
    result = process_movie_entry(
        mock_rss_item, watched_urls, mock_config, 
        request_headers, notion_movies
    )
    
    assert result is False
    mock_select.assert_called_once()


def test_load_config_file_not_found():
    """Test config loading when file doesn't exist"""
    with patch('main.os.path.join') as mock_join:
        mock_join.return_value = '/nonexistent/config.yaml'
        with pytest.raises(FileNotFoundError):
            load_config()