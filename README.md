# Douban Notion Movie Sync 豆瓣Notion电影同步
> 之前电影同步存在一些问题，经过几次修改，现在勉强达到可用状态
> 

This script is designed to track and manage movie information by integrating with various APIs and services. It fetches movie data from Douban RSS feeds, processes the information, and uploads it to a Notion database. The script also interacts with external APIs like TMDb (The Movie Database) and DeepSeek for additional movie details and optimizations.

脚本主要从RSS订阅源获取电影数据，处理信息，并将其上传到Notion数据库。为增加获取体验，脚本还与外部API（如TMDb和DeepSeek）交互，以获取额外的电影详情和优化电影名称。

实现效果如图：
<img width="1371" alt="image" src="https://github.com/user-attachments/assets/f5c82c44-6ee4-48b1-a12e-ab518caf4291" />


## Table of Contents

- [Features]
- [Prerequisites]
- [Configuration]
- [Usage]
- [Functions]
- [Logging]
- [Dependencies]
- [License]

## Features

- **RSS Feed Parsing**: Fetches movie data from a specified RSS feed.
- **Movie Name Optimization**: Uses DeepSeek API to optimize movie names for better searchability.
- **TMDb Integration**: Searches for movie details using TMDb API and retrieves movie posters.
- **Image Handling**: Downloads and compresses movie posters.
- **Notion Integration**: Uploads processed movie data to a Notion database.
- **Logging**: Comprehensive logging for debugging and monitoring.

## Prerequisites

Before running the script, ensure you have the following:

- Python 3.x installed
- API keys for:
    - DeepSeek API (for optional movie name fo tmdb api)
    - TMDb API
    - [SM.MS](http://sm.ms/) (for image hosting *Optional*)
- Notion API token and database ID
- Douban rss address  like
`https://www.douban.com/feed/people/[userid]/interests`

## Configuration

The script uses a `config.yaml` file to store API keys and other configuration settings. Create a `config.yaml` file in the same directory as the script with the following structure:

```yaml
deepseek_api: "your_deepseek_api_key"
tmdb_api_key: "your_tmdb_api_key"
smms_token: "your_smms_token"
rss_address: "your_douban_rss_feed_address"
databaseid: "your_notion_database_id"

```

## Usage

1. **Install Dependencies**:
    
    ```bash
    pip install -r requirements.txt
    
    ```
    
2. **Run the Script**:
    
    ```bash
    python movietracker.py
    
    ```
    
3. **Check Logs**:
The script logs detailed information to the console and a log file. Check the logs for any errors or status updates.

## Functions

### `request_movie_opt_name(moviename)`

- **Description**: Optimizes the movie name using the DeepSeek API for better searchability.
- **Parameters**: `moviename` (str) - The original movie name.
- **Returns**: Optimized movie name.

### `search_movie(api_key, query)`

- **Description**: Searches for a movie using the TMDb API and returns the movie ID.
- **Parameters**:
    - `api_key` (str) - TMDb API key.
    - `query` (str) - Movie name to search.
- **Returns**: Movie ID.

### `get_movie_poster(api_key, movie_id)`

- **Description**: Retrieves the movie poster URL using the TMDb API.
- **Parameters**:
    - `api_key` (str) - TMDb API key.
    - `movie_id` (str) - Movie ID.
- **Returns**: Movie poster URL.

### `compress_image(input_path, max_size_kb=5000)`

- **Description**: Compresses an image to a specified maximum size.
- **Parameters**:
    - `input_path` (str) - Path to the image file.
    - `max_size_kb` (int) - Maximum size in KB (default is 5000 KB).

### `download_img(img_url)`

- **Description**: Downloads an image from a given URL.
- **Parameters**: `img_url` (str) - Image URL.
- **Returns**: Local path to the downloaded image.

### `upload_img(path)`

- **Description**: Uploads an image to [SM.MS](http://sm.ms/) for hosting.
- **Parameters**: `path` (str) - Local path to the image file.
- **Returns**: Image URL after upload.

### `film_info1(item)`

- **Description**: Extracts and processes movie information from an RSS feed item.
- **Parameters**: `item` (dict) - RSS feed item.
- **Returns**: Processed movie information.

### `film_info2(movie_url)`

- **Description**: Fetches additional movie details from a given URL.
- **Parameters**: `movie_url` (str) - Movie URL.
- **Returns**: Additional movie details.

### `remove_year(text)`

- **Description**: Removes the year from a movie title.
- **Parameters**: `text` (str) - Movie title.
- **Returns**: Movie title without the year.

## License

This project is licensed under the MIT License.
