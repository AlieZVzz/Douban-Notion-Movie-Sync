import sys
import os
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest
from unittest.mock import Mock, patch, MagicMock
import requests


def test_notion_api_imports():
    """Test that Notion API functions can be imported"""
    try:
        from src.api.notion_api import (
            delete_page, updata_page_properties, 
            DataBase_additem, DataBase_item_query,
            select_items_form_Databaseid, select_items_form_Databaseitems
        )
        assert True  # If import succeeds, test passes
    except ImportError as e:
        pytest.fail(f"Failed to import Notion API functions: {e}")


def test_tmdb_api_imports():
    """Test that TMDB API functions can be imported"""
    try:
        from src.api.tmdb_api import search_movie, get_movie_poster
        assert True  # If import succeeds, test passes
    except ImportError as e:
        pytest.fail(f"Failed to import TMDB API functions: {e}")


@patch('api.tmdb_api.requests.get')
def test_search_movie_success(mock_get):
    """Test successful movie search"""
    mock_response = Mock()
    mock_response.json.return_value = {
        'results': [{'id': 12345, 'title': 'Inception'}]
    }
    mock_get.return_value = mock_response
    
    from src.api.tmdb_api import search_movie
    result = search_movie('fake_api_key', 'Inception')
    
    assert result == 12345
    mock_get.assert_called_once()


@patch('api.tmdb_api.requests.get')
def test_search_movie_no_results(mock_get):
    """Test movie search with no results"""
    mock_response = Mock()
    mock_response.json.return_value = {'results': []}
    mock_get.return_value = mock_response
    
    from src.api.tmdb_api import search_movie
    result = search_movie('fake_api_key', 'NonExistentMovie')
    
    assert result is None


@patch('api.tmdb_api.requests.get')
def test_get_movie_poster_success(mock_get):
    """Test successful poster retrieval"""
    mock_response = Mock()
    mock_response.json.return_value = {
        'poster_path': '/path/to/poster.jpg'
    }
    mock_get.return_value = mock_response
    
    from src.api.tmdb_api import get_movie_poster
    result = get_movie_poster('fake_api_key', 12345)
    
    assert result == 'https://image.tmdb.org/t/p/w500/path/to/poster.jpg'


@patch('api.tmdb_api.requests.get')
def test_get_movie_poster_no_poster(mock_get):
    """Test poster retrieval when no poster available"""
    mock_response = Mock()
    mock_response.json.return_value = {}
    mock_get.return_value = mock_response
    
    from src.api.tmdb_api import get_movie_poster
    result = get_movie_poster('fake_api_key', 12345)
    
    assert result == "No poster available"