# DoubanNotionSync

将豆瓣电影观看记录同步到 Notion 数据库。

这个项目会从豆瓣 RSS 订阅读取“看过”的电影记录，补充电影标题、导演、类型和海报信息，然后写入 Notion 数据库。项目包含豆瓣页面反爬处理逻辑，也提供了 Docker 打包、服务器部署和每小时定时执行脚本。

## 功能

- 从豆瓣 RSS 拉取电影观看记录
- 过滤已经存在于 Notion 数据库中的影片，避免重复导入
- 访问豆瓣详情页并提取标题、导演、类型等信息
- 调用 TMDb 获取电影海报
- TMDb 无海报时，可选回退到豆瓣封面并上传到 S.EE
- 支持 Docker 单次执行
- 支持服务器 cron 每小时执行一次

## 工作流程

1. 读取 `src/config.yaml`
2. 解析豆瓣 RSS 订阅
3. 查询 Notion 中已有的电影链接
4. 对新电影访问豆瓣详情页并提取补充信息
5. 调用 TMDb 获取海报
6. 组装 Notion 页面属性并写入数据库

## 项目结构

```text
.
├── config.example.yaml
├── Dockerfile
├── docker-compose.yml
├── DEPLOY.md
├── requirements.txt
├── run_tests.py
├── scripts/
│   ├── deploy.sh
│   ├── docker-run-once.sh
│   └── install_hourly_cron.sh
├── src/
│   ├── api/
│   │   ├── notion_api.py
│   │   └── tmdb_api.py
│   ├── config.yaml
│   └── main.py
└── tests/
```

## 环境要求

- Python 3.9+
- Notion Integration Token
- 目标 Notion 数据库
- 豆瓣 RSS 地址，例如 `https://www.douban.com/feed/people/<user_id>/interests`
- TMDb API Key

可选：

- DeepSeek API Key
- S.EE API Key

## 配置

复制配置模板：

```bash
cp config.example.yaml src/config.yaml
```

然后编辑 `src/config.yaml`。

示例：

```yaml
notion_api: "secret_xxx"
databaseid: "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
tmdb_api_key: "your_tmdb_api_key"
rss_address: "https://www.douban.com/feed/people/your_user_id/interests"
deepseek_api: "your_deepseek_api_key"
see_api_key: "your_see_api_key"
```

字段说明：

- `notion_api`: Notion Integration Token
- `databaseid`: 目标 Notion 数据库 ID
- `tmdb_api_key`: TMDb API Key
- `rss_address`: 豆瓣 RSS 订阅地址
- `deepseek_api`: 可选，当前主流程未强依赖
- `see_api_key`: 可选，用于重传豆瓣海报。旧配置 `smms_token` 仍兼容。

## Notion 数据库字段

数据库至少需要包含这些属性名称：

- `名称`，类型 `title`
- `观看时间`，类型 `date`
- `评分`，类型 `select`
- `有啥想说的不`，类型 `rich_text`
- `影片链接`，类型 `url`
- `类型`，类型 `multi_select`
- `导演`，类型 `multi_select`
- `封面`，类型 `files`，建议保留

## 本地运行

安装依赖：

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

执行同步：

```bash
python src/main.py
```

## 测试

运行全部测试：

```bash
python run_tests.py
```

或者直接运行：

```bash
pytest tests -v --tb=short
```

## Docker 使用

准备配置文件：

```bash
cp config.example.yaml src/config.yaml
```

构建镜像：

```bash
docker compose build
```

执行一次同步：

```bash
docker compose run --rm doubannotionsync
```

也可以直接使用脚本：

```bash
./scripts/deploy.sh
./scripts/docker-run-once.sh
```

## 部署到服务器

详细部署说明见 [DEPLOY.md](DEPLOY.md)。

项目当前采用的部署方式是：

- 容器只负责单次执行
- 服务器 cron 负责每小时触发

最短部署流程：

```bash
cp config.example.yaml src/config.yaml
./scripts/deploy.sh --install-cron
```

默认 cron 表达式：

```cron
0 * * * *
```

默认日志文件：

```text
logs/cron.log
```

## 在 Mac 上构建 Linux 镜像

如果你在 Apple Silicon Mac 上使用 OrbStack 或 Docker，准备把镜像发到常见 Linux 服务器，通常需要显式构建 `linux/amd64`：

```bash
docker buildx build \
  --platform linux/amd64 \
  -t doubannotionsync:latest \
  -o type=docker,dest=doubannotionsync-amd64.tar \
  .
```

上传镜像包：

```bash
gzip doubannotionsync-amd64.tar
scp doubannotionsync-amd64.tar.gz user@your-server:/opt/DoubanNotionSync/
```

服务器上加载：

```bash
gunzip doubannotionsync-amd64.tar.gz
docker load -i doubannotionsync-amd64.tar
```

## 常见问题

### 为什么访问豆瓣详情页有时会失败

豆瓣页面存在反爬策略。项目在 `src/main.py` 中实现了授权页解析和 `sol` 计算逻辑，但这类逻辑天然会受豆瓣策略变化影响。

### 为什么海报有时不是 TMDb 的

如果 TMDb 没有返回海报，项目会回退到豆瓣封面。配置了 `see_api_key` 时，会优先上传到 S.EE 再写入 Notion，避免直接引用豆瓣资源。旧配置 `smms_token` 仍可兼容读取。

### 为什么本地构建的镜像在服务器不能直接用

通常是镜像架构不一致。Apple Silicon Mac 更容易默认构建出 `linux/arm64`，而大多数 Linux 云服务器是 `linux/amd64`。这时需要使用 `docker buildx build --platform linux/amd64` 重新构建。
