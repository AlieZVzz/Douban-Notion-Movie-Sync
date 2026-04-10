# -- coding: UTF-8 --
import time
import requests
import urllib.request
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, wait, ALL_COMPLETED


# 该函数用于下载图片
# 传入函数： 网页的网址url
def download_picture(url):
    headers = {
        "Host": "movie.douban.com",
        "Referer": "https://movie.douban.com/top250?start=225&filter=",
        "Upgrade-Insecure-Requests": "1",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/68.0.3440.84 Safari/537.36",
    }
    # 获取网页的源代码
    r = requests.get(url, headers=headers)
    # 利用BeautifulSoup将获取到的文本解析成HTML
    soup = BeautifulSoup(r.text, "lxml")
    # 获取网页中的电影图片
    content = soup.find('div', class_='article')
    images = content.find_all('img')
    # 获取电影图片的名称和下载地址
    picture_name_list = [image['alt'] for image in images]
    picture_link_list = [image['src'] for image in images]
    print(picture_link_list)

    # 利用urllib.request..urlretrieve正式下载图片
    for picture_name, picture_link in zip(picture_name_list, picture_link_list):
        urllib.request.urlretrieve(picture_link, 'E://douban/%s.jpg' % picture_name)
    # return picture_name_list, picture_link_list


def main():
    # 全部10个网页
    start_urls = ["https://movie.douban.com/top250"]
    for i in range(1, 10):
        start_urls.append("https://movie.douban.com/top250?start=%d&filter=" % (25 * i))

    # 统计该爬虫的消耗时间
    print('*' * 50)
    t3 = time.time()

    # 利用并发下载电影图片
    executor = ThreadPoolExecutor(max_workers=10)  # 可以自己调整max_workers,即线程的个数
    # submit()的参数： 第一个为函数， 之后为该函数的传入参数，允许有多个
    future_tasks = [executor.submit(download_picture, url) for url in start_urls]
    # 等待所有的线程完成，才进入后续的执行
    wait(future_tasks, return_when=ALL_COMPLETED)

    t4 = time.time()
    print('使用多线程，总共耗时：%s' % (t4 - t3))
    print('*' * 50)


main()