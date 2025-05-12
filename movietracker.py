import time
import yaml
import os
import re
import feedparser
import requests
from bs4 import BeautifulSoup
import NotionAPI
from PIL import Image
import logging
import json

# 设置日志格式
log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
logging.basicConfig(level=logging.INFO, format=log_format)

# 获取日志器
logger = logging.getLogger("MyLogger")


def request_movie_opt_name(moviename):
    url = "https://api.deepseek.com/chat/completions"

    payload = json.dumps({
        "messages": [
            {
                "role": "user",
                "content": "请将以下的电影名称转换为一个tmdb数据库可以搜索到标准名称" + "\n" + moviename + "\n" +
                           "注意！！！！请直接告诉我名称，，不需要返回其他内容！！，不需要返回其他内容\n" +
                           "例如： 地球脉动 第三季 Planet Earth Season 3(2023)，可以搜索到的名称是 Planet Earth III" +
                           "直接返回 Planet Earth III 即可。不需要返回其他内容！",
            }
        ],
        "model": "deepseek-chat",
        "frequency_penalty": 0,
        "max_tokens": 2048,
        "presence_penalty": 0,
        "response_format": {
            "type": "text"
        },
        "stop": None,
        "stream": False,
        "stream_options": None,
        "temperature": 1,
        "top_p": 1,
        "tools": None,
        "tool_choice": "none",
        "logprobs": False,
        "top_logprobs": None
    })
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Authorization': 'Bearer ' + config["deepseek_api"]
    }

    response = requests.request("POST", url, headers=headers, data=payload)
    if response.status_code == 200:
        logger.info("opt movie name is " + response.json().get("choices")[0].get("message").get("content"))
        logger.info(response.text)
        return response.json().get("choices")[0].get("message").get("content")
    else:
        logger.error("api call failed")
        return moviename


def search_movie(api_key, query):
    """搜索电影并返回第一个搜索结果的电影 ID"""
    url = f'https://api.themoviedb.org/3/search/movie?api_key={api_key}&query={query}'
    response = requests.get(url)
    data = response.json()
    if data['results']:
        return data['results'][0]['id']
    else:
        new_name = request_movie_opt_name(query)
        url = f'https://api.themoviedb.org/3/search/movie?api_key={api_key}&query={new_name}'
        response = requests.get(url)
        data = response.json()
        if data['results']:
            return data['results'][0]['id']
        else:
            logger.warning("searching movie id failed, origin name:%s,new name:%s", query, new_name)
            return None


def get_movie_poster(api_key, movie_id):
    """
    根据电影 ID 获取电影海报 URL
    """
    url = f'https://api.themoviedb.org/3/movie/{movie_id}?api_key={api_key}'
    response = requests.get(url)
    data = response.json()
    if 'poster_path' in data and data['poster_path']:
        poster_path = data['poster_path']
        poster_url = f'https://image.tmdb.org/t/p/w500{poster_path}'
        return poster_url
    else:
        logger.warning("No poster available,{}", movie_id)
        return ""


def compress_image(input_path, max_size_kb=5000):
    """
    压缩图片
    :param input_path:
    :param max_size_kb:
    :return:
    """
    with Image.open(input_path) as img:
        width, height = img.size
        file_size = os.path.getsize(input_path) / 1024  # 转换为KB
        if file_size > max_size_kb:
            compression_ratio = (max_size_kb / file_size) ** 0.5
            new_width = int(width * compression_ratio)
            new_height = int(height * compression_ratio)
            compressed_img = img.resize((new_width, new_height))
            compressed_img = compressed_img.convert("RGB")
            compressed_img.save(input_path)
        else:
            img.save(input_path)


def download_img(img_url):
    """
    download douban cover to local
    :param img_url:
    :return:
    """
    r = requests.get(img_url, headers={'Referer': 'https://movie.douban.com'}, stream=True)
    logger.info(r.status_code)
    img_name = "posters/" + img_url.split("/")[-1]
    if r.status_code == 200:
        with open("posters/" + img_url.split("/")[-1], 'wb') as f:
            for chunk in r.iter_content(chunk_size=2048):
                if chunk:
                    f.write(chunk)
                    f.flush()
        logger.info("download image success")
        return img_name
    else:
        logger.error("下载图片失败")
        return None


def upload_img(path):
    """
    upload img to smms
    :param path:
    :return:
    """
    compress_image(path)
    headers = {'Authorization': config["smms_token"]}
    files = {'smfile': open(path, 'rb')}
    url = 'https://sm.ms/api/v2/upload'
    res = requests.post(url, files=files, headers=headers)
    res = res.json()

    if "data" in res.keys():
        logger.info("upload data success")
        return res['data']['url']


def film_info1(item):
    """名称title 封面链接cover_url 观影时间watch_time 电影链接movive_url 评分score 评论 comment"""
    pattern1 = re.compile(r'(?<=src=").+(?=")', re.I)  # 匹配海报链接
    title = item["title"].split("看过")[1]
    cover_url = re.findall(pattern1, item["summary"])[0]
    cover_url = cover_url.replace("s_ratio_poster", "r")

    # img_file = download_img(cover_url)
    # if img_file is not None:
    #     cover_url = upload_img(img_file)
    # else:
    #     cover_url = None

    time = item["published"]
    pattern2 = re.compile(r'(?<=. ).+\d{4}', re.S)  # 匹配时间
    month_standard = {'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04', 'May': '05', 'Jun': '06',
                       'Jul': '07', 'Aug': '08', 'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'}
    time = re.findall(pattern2, time)[0]
    time = time.split(" ")
    day = time[0]
    month = month_standard[time[1]]
    year = time[2]
    watch_time = str(year) + "-" + str(month) + "-" + str(day)
    # logger.info(watch_time)

    movie_url = item["link"]

    # 处理comment
    pattern = re.compile(r'(?<=<p>).+(?=</p>)', re.S)  # 匹配评论·
    # pattern2 = re.compile(r'(?<=<p>)(.|\n)+(?=</p>)', re.I) # 匹配评论·
    allcomment = re.findall(pattern, item["summary"])[0]  # 需要进一步处理
    # logger.info(allcomment)

    pattern1 = re.compile(r'(?<=推荐: ).+(?=</p>)', re.S)  # 匹配评分
    # 一星：很差 二星：较差 三星：还行 四星：推荐 五星：力荐
    scoredict = {'很差': '⭐', '较差': '⭐⭐', '还行': '⭐⭐⭐', '推荐': '⭐⭐⭐⭐', '力荐': '⭐⭐⭐⭐⭐', }
    # score = re.findall(pattern1, allcomment)
    score = allcomment[-2:]
    if score:
        score = scoredict[score]
    else:
        score = "⭐⭐⭐"
    # logger.info(score)

    # pattern2 = re.compile(r'(?<=<p>).+', re.S)  # 匹配评价
    # comment = re.findall(pattern2, allcomment)[0]
    # comment = comment.split("备注: ")[1]
    comment = ''
    return cover_url, watch_time, movie_url, score, comment


def film_info2(movie_url):
    # 检测网址是否是https，不是的话更改格式为https
    if movie_url[:5] != 'https':
        url = movie_url[:4] + 's' + movie_url[4:]
    else:
        url = movie_url
    res = requests.get(url, headers=headers)
    bstitle = BeautifulSoup(res.text, 'html.parser')

    moive_content = bstitle.find_all('div', id='content')[0]

    # 电影名称与年份
    title = moive_content.find('h1')
    title = title.find_all('span')
    title = title[0].text + title[1].text

    # 基本信息
    base_information = moive_content.find('div', class_='subject clearfix')
    info = base_information.find('div', id='info').text.split('\n')
    info = ','.join(info)

    pattern_type = re.compile(r'(?<=类型: )[\u4e00-\u9fa5 /]+', re.S)
    movie_type = re.findall(pattern_type, info)[0].replace(" ", "").split("/")
    pattern_director = re.compile(r'(?<=导演: )[\u4e00-\u9fa5 /]+', re.I)

    if len(re.findall(pattern_director, info)) > 0:
        director = re.findall(pattern_director, info)[0].replace(" ", "").split("/")
    else:
        director = ""

    logger.info("title:%s,movie_type:%s,director:%s", title, str(movie_type), str(director))

    return title, movie_type, director


def remove_year(text):
    # 正则表达式匹配括号及其中的数字，其中的 \d+ 匹配一个或多个数字
    new_text = re.sub(r'\(\d+\)', '', text)
    return new_text.strip()  # 使用 strip() 去除可能出现的额外空格


# 开始连接notion

# 改进：加入重试机制，加入防止重复
if __name__ == '__main__':
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, 'config.yaml')
    logger.info("reading config file")
    fs = open(config_path, encoding="UTF-8")
    config = yaml.safe_load(fs)

    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
        'Cookie': 'll="108288"; bid=LxuBFcq903Y; _pk_id.100001.8cb4=d9ac29ae35fdb232.1687791343.; _pk_ses.100001.8cb4=1; __utma=30149280.453255204.1687791344.1687791344.1687791344.1; __utmc=30149280; __utmz=30149280.1687791344.1.1.utmcsr=(direct)|utmccn=(direct)|utmcmd=(none); __utmt=1; dbcl2="208462734:1M1epG+m4oE"; ck=O7sa; push_noty_num=0; push_doumail_num=0; __utmv=30149280.20846; __utmb=30149280.5.9.1687791368060; ap_v=0,6.0',
        # 'Host': 'www.douban.com',
        'Content-type': 'text/html; charset=utf-8',
        # 'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
        'Upgrade-Insecure-Requests': '1',
        # 'Accept-Encoding': 'gzip, deflate, br'
    }

    # notion相关配置

    rss_movietracker = feedparser.parse(config["rss_address"], request_headers=headers)
    logger.info(rss_movietracker)
    notion_movies = NotionAPI.DataBase_item_query(config["databaseid"])
    watched_movie = [item['properties']['影片链接']['url'] for item in notion_movies]
    # logger.info("看过的列表有：%s", watched_movie)
    for item in rss_movietracker["entries"]:
        if "看过" not in item["title"]:
            continue
        cover_url, watch_time, movie_url, score, comment = film_info1(item)

        rel = NotionAPI.select_items_form_Databaseitems(notion_movies, "影片链接", movie_url)
        if rel:
            continue
        if movie_url not in watched_movie:
            title, movie_type, director = film_info2(movie_url)
            movie_name = remove_year(title)  # 你想搜索的电影名称
            movie_id = search_movie(config["tmdb_api_key"], movie_name)
            if movie_id:
                poster_url = get_movie_poster(config["tmdb_api_key"], movie_id)
                logger.info(f'Poster URL for "{movie_name}": {poster_url}')
            else:
                logger.warning(f'No results found for "{movie_name}"')
                poster_url = " "

            body = {
                'properties': {
                    '名称': {
                        'title': [{'type': 'text', 'text': {'content': str(title)}}]
                    },
                    '观看时间': {'date': {'start': str(watch_time)}},
                    '评分': {'type': 'select', 'select': {'name': str(score)}},
                    '封面': {
                        'files': [{'type': 'external', 'name': '封面', 'external': {'url': str(poster_url)}}]
                    },
                    '有啥想说的不': {'type': 'rich_text',
                                     'rich_text': [
                                         {'type': 'text', 'text': {'content': str(comment)},
                                          'plain_text': str(comment)}]},
                    '影片链接': {'type': 'url', 'url': str(movie_url)},
                    '类型': {'type': 'multi_select', 'multi_select': [{'name': str(item)} for item in movie_type]},
                    '导演': {'type': 'multi_select', 'multi_select': [{'name': str(item)} for item in director]},

                }
            }
            logger.info(body)
            NotionAPI.DataBase_additem(config["databaseid"], body, title)
            time.sleep(3)
