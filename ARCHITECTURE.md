# DoubanNotionSync 架构说明

## 运行流程

1. `src.main` 加载并验证 YAML 配置，可由环境变量覆盖密钥。
2. `SyncService` 在共享超时和重试策略下获取豆瓣 RSS。
3. `DoubanClient` 读取详情页；详情页暂时不可用时，使用 RSS 标题安全降级。
4. `TMDBClient` 使用名称和年份匹配海报；找不到时可将豆瓣封面转存到 S.EE。
5. `NotionClient` 使用 `has_more` 和 `next_cursor` 获取全部已同步链接。
6. Notion 返回有效页面 ID 后才计为新增，并立即更新本次运行的去重集合。

## 模块职责

- `src/config.py`：配置加载、环境变量覆盖和启动前校验。
- `src/http_client.py`：连接池、限流响应和临时网络故障重试。
- `src/api/notion_api.py`：Notion 查询、分页、写入和请求体构造。
- `src/api/tmdb_api.py`：TMDB 搜索和海报地址解析。
- `src/douban.py`：RSS 数据、豆瓣详情和反爬挑战解析。
- `src/posters.py`：海报下载、压缩、转存和临时文件清理。
- `src/sync_service.py`：业务编排、去重、失败隔离、统计和运行锁。

## 失败语义

- RSS 无法读取或为空：整个任务失败并返回非零退出码。
- 单条电影无法写入：继续处理其他电影，任务最终返回非零退出码。
- 豆瓣详情页不可用：保留 RSS 标题并继续同步，不创建空标题。
- TMDB 或图床不可用：继续同步其他字段，封面留空。
- 已有任务持有运行锁：本次退出，不重复运行。

## 验证

```bash
python run_tests.py
uv run ruff check src tests
docker compose config
```

`run_tests.py` 会把开发环境放在系统临时目录，避免 OneDrive 按需文件影响虚拟环境。

GitHub Actions 会在 push 和 pull request 时重复执行测试、Ruff、Python 包构建和
Docker 镜像构建。
