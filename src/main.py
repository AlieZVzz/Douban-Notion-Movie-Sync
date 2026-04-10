"""
豆瓣电影同步至 Notion 数据库
Sync Douban movie tracking to Notion database
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
from datetime import datetime
from typing import Any, Optional
from urllib.parse import urlencode, parse_qs, quote

import feedparser
import requests
import yaml
from bs4 import BeautifulSoup
from PIL import Image

from api.notion_api import *
from api.tmdb_api import search_movie, get_movie_poster

# ==================== 常量定义 ====================
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s"
TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w500"
DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
SMMS_UPLOAD_URL = "https://sm.ms/api/v2/upload"
POSTERS_DIR = "posters"

# 预编译正则表达式 (避免重复编译)
RE_POSTER_URL = re.compile(r'(?<=src=").+(?=")', re.I)
RE_PUB_TIME = re.compile(r'(?<=. ).+\d{4}', re.S)
RE_COMMENT = re.compile(r'(?<=<p>).+(?=</p>)', re.S)
RE_MOVIE_TYPE = re.compile(r'(?<=类型: )[\u4e00-\u9fa5 /]+', re.S)
RE_DIRECTOR = re.compile(r'(?<=导演: )[\u4e00-\u9fa5 /]+', re.I)
RE_YEAR_IN_PARENS = re.compile(r'\(\d+\)')

# 月份映射
MONTH_MAP = {
    'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04',
    'May': '05', 'Jun': '06', 'Jul': '07', 'Aug': '08',
    'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'
}

# 评分映射
SCORE_MAP = {
    '很差': '⭐', '较差': '⭐⭐', '还行': '⭐⭐⭐',
    '推荐': '⭐⭐⭐⭐', '力荐': '⭐⭐⭐⭐⭐'
}

DEFAULT_SCORE = "⭐⭐⭐"

# ==================== 日志配置 ====================
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger("MovieTracker")

# ==================== 全局会话 (连接复用) ====================
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36',
    'Accept': 'application/json',
    'Referer': 'https://movie.douban.com'})


def load_config() -> dict[str, Any]:
    """加载配置文件"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, 'config.yaml')
    logger.info("Reading configuration file")
    with open(config_path, encoding="UTF-8") as f:
        return yaml.safe_load(f)


def request_movie_opt_name(moviename: str, api_key: str) -> str:
    """使用 DeepSeek API 优化电影名称以便 TMDB 搜索"""
    logger.debug(f"Requesting optimized name for movie: {moviename}")

    payload = {
        "messages": [{
            "role": "user",
            "content": (
                f"请将以下的电影名称转换为一个tmdb数据库可以搜索到标准名称\n{moviename}\n"
                "注意！！！！请直接告诉我名称，不需要返回其他内容！！\n"
                "例如： 地球脉动 第三季 Planet Earth Season 3(2023)，可以搜索到的名称是 Planet Earth III\n"
                "直接返回 Planet Earth III 即可。不需要返回其他内容！"
            ),
        }],
        "model": "deepseek-chat",
        "frequency_penalty": 0,
        "max_tokens": 2048,
        "presence_penalty": 0,
        "response_format": {"type": "text"},
        "stream": False,
        "temperature": 1,
        "top_p": 1,
    }

    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Authorization': f'Bearer {api_key}'
    }

    try:
        response = session.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=30)
        if response.status_code == 200:
            optimized_name = response.json()["choices"][0]["message"]["content"]
            logger.info(f"Successfully optimized movie name: {moviename} -> {optimized_name}")
            return optimized_name
        else:
            logger.error(f"Failed to optimize movie name. Status: {response.status_code}")
            return moviename
    except Exception as e:
        logger.error(f"Exception while requesting optimized movie name: {e}")
        return moviename


def compute_sol(cha: str, difficulty: int = 4) -> int:
    """
    计算豆瓣反爬验证的 sol 值
    通过找到一个 nonce，使得 SHA-512(cha + nonce) 的前 difficulty 位都是 0
    difficulty 通常为 4
    """
    logger.debug(f"Computing sol value with difficulty={difficulty}")
    nonce = 0
    target_prefix = '0' * difficulty
    
    while True:
        nonce += 1
        # 计算 SHA-512 哈希
        hash_input = (cha + str(nonce)).encode('utf-8')
        hash_value = hashlib.sha512(hash_input).hexdigest()
        
        # 检查前缀是否匹配
        if hash_value.startswith(target_prefix):
            logger.debug(f"Found sol={nonce} for cha (hash starts with {target_prefix})")
            return nonce
        
        # 防止无限循环
        if nonce > 10000000:
            logger.error("Failed to find sol within reasonable time")
            raise Exception("Cannot compute sol value")


def fetch_douban_page_with_auth(url: str, headers: dict[str, str]) -> str:
    """
    获取豆瓣页面内容，处理新的反爬策略
    
    流程：
    1. 首次请求会被 302 重定向到授权页面
    2. 从授权页面提取 tok 和 cha
    3. 使用 SHA-512 计算 sol 值
    4. 提交表单到 https://sec.douban.com/c 获取授权 cookie
    5. 使用授权 cookie 重新请求目标页面
    """
    logger.debug(f"Fetching Douban page with anti-crawl handling: {url}")
    
    # 确保使用 HTTPS
    url = url if url.startswith('https') else url.replace('http', 'https', 1)
    
    # 第一步：首次请求，会被 302 重定向
    try:
        response = session.get(url, headers=headers, allow_redirects=False, timeout=30)
        
        # 如果不是 302，直接返回成功的响应
        if response.status_code == 200:
            logger.debug("Direct access successful, no auth required")
            return response.text
        
        # 如果是 302，获取授权地址
        if response.status_code == 302:
            auth_url = response.headers.get('Location')
            if not auth_url:
                logger.error("302 redirect but no Location header")
                raise Exception("Empty redirect location")
            
            logger.info(f"Redirected to auth page: {auth_url}")
            
            # 第二步：访问授权页面，获取表单数据
            auth_response = session.get(auth_url, headers=headers, timeout=30)
            auth_soup = BeautifulSoup(auth_response.text, 'html.parser')
            
            # 提取表单数据
            form = auth_soup.find('form', {'id': 'sec'})
            if not form:
                logger.error("Cannot find auth form")
                raise Exception("Auth form not found")
            
            tok = form.find('input', {'id': 'tok'})
            cha = form.find('input', {'id': 'cha'})
            
            if not tok or not cha:
                logger.error("Cannot find tok or cha fields")
                raise Exception("Missing tok or cha fields")
            
            tok_value = tok.get('value', '')
            cha_value = cha.get('value', '')
            red_value = form.find('input', {'id': 'red'}).get('value', '')
            
            logger.debug(f"Extracted tok (first 50 chars): {tok_value[:50]}...")
            logger.debug(f"Extracted cha: {cha_value}")
            
            # 第三步：计算 sol 值
            try:
                sol_value = compute_sol(cha_value)
                logger.info(f"Computed sol={sol_value}")
            except Exception as e:
                logger.error(f"Failed to compute sol: {e}")
                raise
            
            # 第四步：提交表单到 https://sec.douban.com/c
            challenge_url = 'https://sec.douban.com/c'
            payload = {
                'tok': tok_value,
                'cha': cha_value,
                'sol': str(sol_value),
                'red': red_value
            }
            
            logger.debug(f"Submitting challenge to {challenge_url}")
            challenge_response = session.post(
                challenge_url,
                data=payload,
                headers=headers,
                allow_redirects=False,
                timeout=30
            )
            
            # 检查是否成功получ授权
            if challenge_response.status_code == 302:
                logger.info("Challenge passed, authorization cookie obtained")
                # 服务器会在 Set-Cookie 中返回 dbsawcv1
                # session 会自动保存 cookie
            else:
                logger.warning(f"Challenge response status: {challenge_response.status_code}")
            
            # 第五步：使用授权后的 session（包含 cookie）重新请求目标页面
            final_response = session.get(url, headers=headers, timeout=30)
            
            if final_response.status_code == 200:
                logger.info("Successfully fetched Douban page after authorization")
                return final_response.text
            else:
                logger.error(f"Final request failed with status {final_response.status_code}")
                raise Exception(f"Failed to fetch page after authorization: {final_response.status_code}")
        
        else:
            logger.error(f"Unexpected status code: {response.status_code}")
            raise Exception(f"Unexpected response status: {response.status_code}")
    
    except Exception as e:
        logger.error(f"Error fetching Douban page: {e}")
        raise



def compress_image(input_path: str, max_size_kb: int = 5000) -> None:
    """压缩图片至指定大小以下"""
    logger.debug(f"Compressing image: {input_path}")
    try:
        file_size = os.path.getsize(input_path) / 1024
        logger.debug(f"Original image size: {file_size:.2f} KB")

        if file_size <= max_size_kb:
            logger.debug("Image size is within limit, no compression needed")
            return

        with Image.open(input_path) as img:
            compression_ratio = (max_size_kb / file_size) ** 0.5
            new_size = (int(img.width * compression_ratio), int(img.height * compression_ratio))
            compressed_img = img.resize(new_size).convert("RGB")
            compressed_img.save(input_path)

        new_file_size = os.path.getsize(input_path) / 1024
        logger.info(f"Compressed image from {file_size:.2f} KB to {new_file_size:.2f} KB")
    except Exception as e:
        logger.error(f"Exception while compressing image: {e}")


def download_img(img_url: str) -> Optional[str]:
    """下载豆瓣封面图片到本地"""
    logger.info(f"Downloading image from: {img_url}")
    try:
        response = session.get(
            img_url,
            headers={'Referer': 'https://movie.douban.com'},
            stream=True,
            timeout=30
        )

        if response.status_code != 200:
            logger.error(f"Failed to download image. Status: {response.status_code}")
            return None

        img_name = os.path.join(POSTERS_DIR, img_url.split("/")[-1])
        with open(img_name, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        logger.info(f"Successfully downloaded image to: {img_name}")
        return img_name
    except Exception as e:
        logger.error(f"Exception while downloading image: {e}")
        return None


def upload_img(path: str, smms_token: str) -> Optional[str]:
    """上传图片到 SM.MS 图床"""
    logger.info(f"Uploading image: {path}")
    try:
        compress_image(path)
        headers = {'Authorization': smms_token}

        with open(path, 'rb') as f:
            response = session.post(SMMS_UPLOAD_URL, files={'smfile': f}, headers=headers, timeout=60)
            result = response.json()

        if "data" in result:
            uploaded_url = result['data']['url']
            logger.info(f"Successfully uploaded image. URL: {uploaded_url}")
            return uploaded_url

        logger.error(f"Failed to upload image. Response: {result}")
        return None
    except Exception as e:
        logger.error(f"Exception while uploading image: {e}")
        return None


def parse_rss_item(item: dict[str, Any]) -> tuple[str, str, str, str, str]:
    """
    解析 RSS 条目，提取电影基本信息
    返回: (cover_url, watch_time, movie_url, score, comment)
    """
    logger.debug("Extracting film info from RSS item")

    # 提取标题和封面
    title = item["title"].split("看过")[1]
    
    # 提取封面 URL (带防御性检查)
    poster_matches = RE_POSTER_URL.findall(item.get("summary", ""))
    if not poster_matches:
        logger.warning(f"No poster URL found for: {title}")
        cover_url = ""
    else:
        cover_url = poster_matches[0].replace("s_ratio_poster", "r")
    logger.debug(f"Extracted cover URL: {cover_url}")

    # 解析观看时间 (带防御性检查)
    pub_time = item.get("published", "")
    time_matches = RE_PUB_TIME.findall(pub_time)
    if not time_matches:
        logger.warning(f"No publish time found for: {title}, using current date")
        from datetime import date
        watch_time = date.today().isoformat()
    else:
        time_parts = time_matches[0].split(" ")
        if len(time_parts) >= 3:
            day, month_str, year = time_parts[0], time_parts[1], time_parts[2]
            watch_time = f"{year}-{MONTH_MAP.get(month_str, '01')}-{day}"
        else:
            from datetime import date
            watch_time = date.today().isoformat()
    logger.debug(f"Extracted watch time: {watch_time}")

    movie_url = item.get("link", "")
    logger.debug(f"Extracted movie URL: {movie_url}")

    # 提取评分 (带防御性检查)
    comment_matches = RE_COMMENT.findall(item.get("summary", ""))
    if comment_matches:
        score_text = comment_matches[0][-2:]
        score = SCORE_MAP.get(score_text, DEFAULT_SCORE)
    else:
        logger.warning(f"No score found for: {title}, using default")
        score = DEFAULT_SCORE

    comment = ''
    logger.debug("Successfully extracted film info")
    return cover_url, watch_time, movie_url, score, comment


def fetch_movie_details(movie_url: str, request_headers: dict[str, str]) -> tuple[str, list[str], list[str]]:
    """
    从豆瓣页面获取电影详细信息
    返回: (title, movie_types, directors)
    """
    logger.info(f"Fetching detailed film info from: {movie_url}")

    # 确保使用 HTTPS
    url = movie_url if movie_url.startswith('https') else movie_url.replace('http', 'https', 1)

    # 使用新的反爬处理函数获取页面内容
    try:
        page_content = fetch_douban_page_with_auth(url, request_headers)
    except Exception as e:
        logger.error(f"Failed to fetch Douban page with auth: {e}")
        return '', [], []
    
    soup = BeautifulSoup(page_content, 'html.parser')


    content = soup.find('div', id='content')
    if content is None:
        logger.error('No content found in movie page')
        return '', [], []

    # 提取电影名称与年份
    title_element = content.find('h1') if content else None
    if title_element is None:
        logger.error('No h1 found in content')
        return '', [], []
    title_spans = title_element.find_all('span')
    if len(title_spans) < 2:
        logger.error('Not enough span elements in h1 for title')
        return '', [], []
    title = title_spans[0].text + title_spans[1].text

    # 提取基本信息
    base_info = content.find('div', class_='subject clearfix') if content else None
    if base_info is None:
        logger.error('No subject clearfix found in content')
        info_text = ''
    else:
        info_div = base_info.find('div', id='info')
        info_text = ','.join(info_div.text.split('\n')) if info_div else ''

    # 提取类型
    type_match = RE_MOVIE_TYPE.findall(info_text)
    movie_types = type_match[0].replace(" ", "").split("/") if type_match else []

    # 提取导演
    director_match = RE_DIRECTOR.findall(info_text)
    directors = director_match[0].replace(" ", "").split("/") if director_match else []

    logger.info(f"Extracted - Title: {title}, Type: {movie_types}, Director: {directors}")
    return title, movie_types, directors


def remove_year(text: str) -> str:
    """移除文本中括号内的年份"""
    # Remove year patterns like (2010), (1999), etc.
    result = RE_YEAR_IN_PARENS.sub('', text)
    # Clean up extra spaces that might be left behind
    return ' '.join(result.split()).strip()


def build_notion_body(
    title: str,
    watch_time: str,
    score: str,
    poster_url: str,
    comment: str,
    movie_url: str,
    movie_types: list[str],
    directors: list[str]
) -> dict[str, Any]:
    """构建 Notion 数据库条目的请求体"""
    properties = {
        '名称': {'title': [{'type': 'text', 'text': {'content': title}}]},
        '观看时间': {'date': {'start': watch_time}},
        '评分': {'type': 'select', 'select': {'name': score}},
        '有啥想说的不': {'type': 'rich_text', 'rich_text': [{'type': 'text', 'text': {'content': comment}, 'plain_text': comment}]},
        '影片链接': {'type': 'url', 'url': movie_url},
        '类型': {'type': 'multi_select', 'multi_select': [{'name': t} for t in movie_types]},
        '导演': {'type': 'multi_select', 'multi_select': [{'name': d} for d in directors]},
    }
    
    # 只有当 poster_url 有效时才添加封面字段
    if poster_url and poster_url.strip():
        properties['封面'] = {'files': [{'type': 'external', 'name': '封面', 'external': {'url': poster_url}}]}
    
    return {'properties': properties}


def process_movie_entry(
    item: dict[str, Any],
    watched_urls: set[str],
    config: dict[str, Any],
    request_headers: dict[str, str],
    notion_movies: list[dict]
) -> bool:
    """
    处理单个电影条目
    返回: 是否成功添加到 Notion
    """
    cover_url, watch_time, movie_url, score, comment = parse_rss_item(item)

    # 检查是否已存在 (使用 set 进行 O(1) 查找)
    if movie_url in watched_urls:
        logger.debug(f"Movie already exists: {movie_url}")
        return False

    # 额外的数据库查询确认
    from api.notion_api import select_items_form_Databaseitems
    if select_items_form_Databaseitems(notion_movies, "影片链接", movie_url):
        logger.debug(f"Movie already in database: {movie_url}")
        return False

    # 获取详细信息
    title, movie_types, directors = fetch_movie_details(movie_url, request_headers)
    movie_name = remove_year(title)

    # 获取海报 (优先使用 TMDB，fallback 到豆瓣封面)
    movie_id = search_movie(
        config["tmdb_api_key"],
        movie_name
    )

    # 如果需要 DeepSeek optimization, we'll handle it differently
    # if not movie_id and config.get("deepseek_api"):
    #     logger.warning(f"No results for '{movie_name}', attempting to optimize name...")
    #     deepseek_api_key = config.get("deepseek_api") or ""
    #     if not isinstance(deepseek_api_key, str):
    #         deepseek_api_key = str(deepseek_api_key)
    #     new_name = request_movie_opt_name(movie_name, deepseek_api_key)
    #     logger.info(f"Retrying with optimized name: {new_name}")
    #     movie_id = search_movie(config["tmdb_api_key"], new_name)

    poster_url = ""
    if movie_id:
        poster_url = get_movie_poster(config["tmdb_api_key"], movie_id)
    
    # 如果 TMDB 没有海报，使用豆瓣封面作为 fallback
    # 通过下载到本地并上传到 SM.MS 来规避豆瓣 418 限制
    if not poster_url and cover_url:
        logger.info(f'Downloading Douban cover and uploading to SM.MS for "{movie_name}"')
        # 下载豆瓣图片到本地
        local_img_path = download_img(cover_url)
        if local_img_path and config.get("smms_token"):
            # 上传到 SM.MS
            smms_token = config["smms_token"]
            uploaded_url = upload_img(local_img_path, smms_token)
            if uploaded_url:
                poster_url = uploaded_url
                logger.info(f'Successfully uploaded Douban cover to SM.MS for "{movie_name}": {poster_url}')
                # 清理本地文件
                try:
                    os.remove(local_img_path)
                except Exception as e:
                    logger.warning(f"Failed to remove local image: {e}")
            else:
                logger.warning(f'Failed to upload image to SM.MS for "{movie_name}", using original URL')
                poster_url = cover_url
        else:
            if not local_img_path:
                logger.warning(f'Failed to download image for "{movie_name}", using original URL')
            else:
                logger.warning(f'SM.MS token not configured, using original Douban URL')
            poster_url = cover_url
    elif poster_url:
        logger.info(f'TMDB Poster URL for "{movie_name}": {poster_url}')
    else:
        logger.warning(f'No poster found for "{movie_name}"')

    # 构建并添加条目 (如果没有海报，不包含封面字段)
    body = build_notion_body(
        title, watch_time, score, poster_url, comment,
        movie_url, movie_types, directors
    )

    logger.debug(f"Adding movie to Notion: {title}")
    DataBase_additem(config["databaseid"], body, title)
    return True


def main() -> None:
    """主函数"""
    config = load_config()
    
    # 确保 posters 目录存在
    if not os.path.exists(POSTERS_DIR):
        os.makedirs(POSTERS_DIR)
        logger.info(f"Created directory: {POSTERS_DIR}")

    request_headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36',
        'Upgrade-Insecure-Requests': '1',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9',
        'Refer': 'https://www.douban.com/'
    }

    # 解析 RSS
    logger.info("Parsing RSS feed")

    rss_data = feedparser.parse(config["rss_address"], request_headers=request_headers)
    entries = rss_data.get('entries', [])
    if not entries:
        logger.warning("No entries found in RSS feed.")
        entries = []
    logger.info(f"RSS parsing completed. Found {len(entries)} entries")

    # 查询已有电影 (使用 set 优化查找性能)
    logger.info("Querying Notion database for existing movies")

    from api.notion_api import DataBase_item_query
    notion_movies = DataBase_item_query(config["databaseid"])
    watched_urls: set[str] = set()
    for item in notion_movies:
        try:
            url = item['properties']['影片链接'].get('url')
            if url:
                watched_urls.add(url)
        except Exception as e:
            logger.warning(f"Error extracting url from notion_movies item: {e}")
    logger.info(f"Found {len(watched_urls)} existing movies in Notion database")

    # 处理条目
    added_count = 0


    for idx, item in enumerate(entries if entries else []):
        if not item or not isinstance(item, dict):
            continue
        title_val = item.get("title", "")
        if not isinstance(title_val, str):
            title_val = str(title_val) if title_val is not None else ""
        if "看过" not in title_val:
            continue

        logger.info(f"Processing item {idx + 1}: {title_val}")

        try:
            if process_movie_entry(item, watched_urls, config, request_headers, notion_movies):
                added_count += 1
                time.sleep(3)  # API 限流保护
        except Exception as e:
            logger.error(f"Error processing '{item['title']}': {e}")
            continue

    logger.info(f"Processing completed. Added {added_count} new movies")


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        logger.critical(f"Critical error in main execution: {e}")
        raise