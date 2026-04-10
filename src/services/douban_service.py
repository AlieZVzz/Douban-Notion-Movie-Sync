import os

import requests

# 豆瓣电影页面 URL
douban_url = "https://movie.douban.com/subject/26733371/"  # 示例：肖申克的救赎


def get_douban_movie_info(douban_url):
    """从豆瓣电影页面解析电影名称和年份"""
    response = requests.get(douban_url, headers={"User-Agent": "Mozilla/5.0"})
    if response.status_code != 200:
        raise Exception("无法访问豆瓣页面")

    # 简单解析电影名称和年份
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(response.text, "html.parser")
    title = soup.find("span", {"property": "v:itemreviewed"}).text
    year = soup.find("span", {"class": "year"}).text.strip("()")
    return title, year


def get_tmdb_movie_id(title, year, tmdb_api_key):
    """使用 TMDb API 搜索电影并返回 TMDb ID"""
    url = f"https://api.themoviedb.org/3/search/movie"
    params = {
        "api_key": tmdb_api_key,
        "query": title,
        "year": year
    }
    response = requests.get(url, params=params)
    if response.status_code != 200:
        raise Exception("无法访问 TMDb API")

    data = response.json()
    if data["results"]:
        # 返回最相关的电影 ID
        return data["results"][0]["id"]
    return None


# 从环境变量读取 TMDb API Key，避免明文写入仓库
tmdb_api_key = os.getenv("TMDB_API_KEY", "")

# 执行
try:
    if not tmdb_api_key:
        raise Exception("缺少 TMDB_API_KEY 环境变量")

    title, year = get_douban_movie_info(douban_url)
    print(f"电影名称: {title}, 上映年份: {year}")

    tmdb_id = get_tmdb_movie_id(title, year, tmdb_api_key)
    if tmdb_id:
        print(f"对应的 TMDb ID: {tmdb_id}")
    else:
        print("未找到对应的 TMDb 电影")
except Exception as e:
    print(f"发生错误: {e}")
