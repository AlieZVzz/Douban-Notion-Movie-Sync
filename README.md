# DoubanNotionSync

把豆瓣 RSS 中标记为“看过”的电影同步到 Notion 数据库，并补充豆瓣详情、TMDB
海报、类型和导演信息。

## 功能

- 使用影片链接去重，避免重复写入。
- 正确遍历 Notion 数据库的所有分页。
- 豆瓣详情页不可用时，使用 RSS 标题安全降级。
- TMDB 海报不可用时，可选将豆瓣封面转存到 S.EE。
- 网络请求包含超时、连接池和只读请求重试。
- 单条记录失败不会阻断其他记录，最终通过退出码报告失败。
- 文件锁避免多个 cron 任务同时执行。
- 支持 Docker 单次运行和服务器 cron 定时触发。

## 配置

复制示例配置：

```bash
cp config.example.yaml src/config.yaml
```

至少填写：

```yaml
notion_api: "secret_xxx"
databaseid: "notion_database_id"
tmdb_api_key: "tmdb_api_key"
rss_address: "https://www.douban.com/feed/people/your_user_id/interests"
```

可选配置包括 S.EE API Key、请求超时、重试次数、处理间隔和 Notion 属性名称。
完整字段参见 `config.example.yaml`。

以下环境变量可以覆盖 YAML 中的敏感配置：

- `NOTION_API_TOKEN`
- `NOTION_DATABASE_ID`
- `TMDB_API_KEY`
- `DOUBAN_RSS_ADDRESS`
- `SEE_API_KEY`
- `DOUBAN_NOTION_CONFIG`

## 本地运行

使用 uv 安装依赖并执行：

```bash
uv sync
uv run doubannotionsync
```

也可以直接运行入口：

```bash
uv run python -m src.main
```

## 测试

```bash
python run_tests.py
uv run ruff check src tests run_tests.py main.py
```

## Docker

构建并手动执行一次：

```bash
./scripts/deploy.sh
./scripts/docker-run-once.sh
```

安装每小时运行的 cron：

```bash
./scripts/install_hourly_cron.sh
```

更完整的服务器说明参见 `DEPLOY.md`，模块设计和失败语义参见
`ARCHITECTURE.md`。

## Notion 数据库字段

默认字段为：

- `名称`：标题
- `观看时间`：日期
- `评分`：单选
- `有啥想说的不`：文本
- `影片链接`：URL
- `类型`：多选
- `导演`：多选
- `封面`：文件

字段名可以通过 `notion_properties` 配置覆盖。
