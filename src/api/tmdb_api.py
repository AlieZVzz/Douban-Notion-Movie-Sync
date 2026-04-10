import requests


def search_movie(api_key, query):
    """搜索电影并返回第一个搜索结果的电影 ID"""
    url = f'https://api.themoviedb.org/3/search/movie?api_key={api_key}&query={query}'
    response = requests.get(url)
    data = response.json()
    if data['results']:
        return data['results'][0]['id']
    else:
        return None


def get_movie_poster(api_key, movie_id):
    """根据电影 ID 获取电影海报 URL"""
    url = f'https://api.themoviedb.org/3/movie/{movie_id}?api_key={api_key}'
    response = requests.get(url)
    data = response.json()
    if 'poster_path' in data and data['poster_path']:
        poster_path = data['poster_path']
        poster_url = f'https://image.tmdb.org/t/p/w500{poster_path}'
        return poster_url
    else:
        return "No poster available"
