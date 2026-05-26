# 服务器部署说明

这个项目已经改成了“镜像单次执行，服务器 cron 每小时触发一次”的模式。

## 1. 服务器准备

- 安装 Docker
- 安装 Docker Compose 插件，确保 `docker compose` 可用
- 建议把项目放到固定目录，例如 `/opt/DoubanNotionSync`

## 2. 上传项目

把整个仓库上传到服务器，例如：

```bash
scp -r DoubanNotionSync user@your-server:/opt/
ssh user@your-server
cd /opt/DoubanNotionSync
```

## 3. 配置密钥

按示例文件创建配置：

```bash
cp config.example.yaml src/config.yaml
```

然后编辑 `src/config.yaml`，至少填入：

- `notion_api`
- `databaseid`
- `tmdb_api_key`
- `rss_address`

可选项：

- `deepseek_api`
- `see_api_key`

## 4. 构建镜像

```bash
./scripts/deploy.sh
```

如果想构建后直接安装每小时任务：

```bash
./scripts/deploy.sh --install-cron
```

## 5. 手动验证一次

先确保能单次跑通：

```bash
./scripts/docker-run-once.sh
```

如果需要查看容器日志，重新执行时终端会直接输出。

## 6. 安装每小时定时任务

```bash
./scripts/install_hourly_cron.sh
```

安装后会写入当前用户的 crontab，执行频率为每小时整点一次：

```cron
0 * * * *
```

日志输出到：

```bash
logs/cron.log
```

## 7. 常用运维命令

查看当前 cron：

```bash
crontab -l
```

查看最近日志：

```bash
tail -n 100 logs/cron.log
```

重新构建镜像：

```bash
./scripts/deploy.sh
```

手动补跑一次：

```bash
./scripts/docker-run-once.sh
```
