# 豆瓣爬虫反爬策略改造总结

## 改造内容

### 1. 改造的核心函数

#### `compute_sol(cha: str, difficulty: int = 4) -> int`
- **功能**: 计算豆瓣反爬脑机验证的 `sol` 值
- **原理**: 通过找到一个 nonce，使得 `SHA-512(cha + nonce)` 的前 difficulty 位都是 0
- **实现**: 从 nonce=1 开始循环，直到找到匹配的值

#### `fetch_douban_page_with_auth(url: str, headers: dict[str, str]) -> str`
- **功能**: 获取豆瓣页面内容，完整处理新的反爬策略
- **流程**:
  1. 首次请求会被 302 重定向到授权页面
  2. 从授权页面提取 `tok`、`cha`、`red` 字段
  3. 使用 SHA-512 计算 `sol` 值
  4. 提交表单到 `https://sec.douban.com/c`
  5. 获取授权 cookie (`dbsawcv1`)
  6. 使用授权 cookie 重新请求目标页面

### 2. 改造的现有函数

#### `fetch_movie_details()`
- **改动**: 将 `response = session.get(url, headers=request_headers)` 改造为使用 `fetch_douban_page_with_auth()`
- **好处**: 自动处理豆瓣的反爬连接过程

### 3. 关键改进

1. **全局会话复用** (连接复用):
   - 使用全局 `session` 对象确保整个授权流程中 IP 地址不变
   - 自动保存和复用 cookie

2. **完整的授权流程**:
   - 一次完整的 SHA-512 计算可能需要 1-2 秒
   - 获取的 `dbsawcv1` cookie 有效期为 5 分钟
   - 建议对同一 IP 的多个请求共享授权信息

3. **错误处理**:
   - 详细的日志记录整个过程
   - 异常捕获和错误报告

## 技术细节

### SHA-512 计算算法
```
target_prefix = '0000'  (4个零)
nonce = 0
while True:
    nonce += 1
    hash = SHA-512(cha + str(nonce))
    if hash.startswith(target_prefix):
        return nonce
```

### HTTP 请求流程
```
1. GET /subject/xxxxx/ → 302 Location: /auth?xxx
2. GET /auth?xxx → 200 (HTML with form: tok, cha, red, sol)
3. POST /c (tok, cha, sol, red) → 302 + Set-Cookie: dbsawcv1=xxx
4. GET /subject/xxxxx/ (with dbsawcv1) → 200
```

## 使用建议

1. **合理使用缓存**: 同一 cookie 在 5 分钟内可以重复使用
2. **避免频繁请求**: 建议在请求间隔添加延迟 (已在代码中添加)
3. **监控日志**: 查看详细的授权过程日志

## 测试

参考 `test_anti_crawl.py` 文件中的 SHA-512 计算验证
