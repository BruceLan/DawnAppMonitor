# 部署指南

本文档详细说明如何将 Apple 应用监控系统部署到 GitHub Actions。

## 部署到 GitHub Actions

### 优势

- ✅ 免费（每月 2000 分钟执行时间）
- ✅ 自动定时执行
- ✅ 无需服务器
- ✅ 日志完整可查

### 步骤 1：准备代码

#### 方式 A：Fork 仓库

1. 访问原仓库
2. 点击右上角 "Fork" 按钮
3. Fork 到你的 GitHub 账号

#### 方式 B：上传代码

1. 在 GitHub 创建新仓库
2. 将代码上传到仓库：

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/your-username/your-repo.git
git push -u origin main
```

### 步骤 2：配置 GitHub Secrets

在 GitHub 仓库中配置环境变量：

1. 进入仓库 **Settings** -> **Secrets and variables** -> **Actions**
2. 点击 **"New repository secret"** 添加以下密钥：

#### 必需配置

| Secret 名称 | 说明 | 获取方式 |
|------------|------|---------|
| `FEISHU_APP_ID` | 飞书应用 ID | 飞书开放平台 -> 应用详情 |
| `FEISHU_APP_SECRET` | 飞书应用密钥 | 飞书开放平台 -> 应用详情 |
| `FEISHU_WIKI_URL` | 飞书多维表格 URL | 复制多维表格的完整 URL |

**注意：** GitHub Actions 默认为生产环境（`ENV=production`），无需配置 `ENV`。

#### 可选配置（飞书通知）

| Secret 名称 | 说明 | 示例值 |
|------------|------|--------|
| `FEISHU_CHAT_ID_ALL` | @所有人的群聊 ID | `oc_xxx` |
| `FEISHU_CHAT_ID_TEAM` | @指定用户的群聊 ID | `oc_yyy` |
| `FEISHU_MENTION_USERS` | 要 @ 的用户 ID（逗号分隔） | `ou_aaa,ou_bbb` |

### 步骤 3：启用 GitHub Actions

1. 进入仓库 **Actions** 标签页
2. 如果提示启用 Workflows，点击 **"I understand my workflows, go ahead and enable them"**
3. 工作流会自动每小时执行一次

### 步骤 4：验证部署

#### 手动触发测试

1. 进入 **Actions** 页面
2. 选择 **"Apple App Monitor"** 工作流
3. 点击 **"Run workflow"** -> **"Run workflow"**
4. 等待执行完成，查看日志

#### 查看执行日志

1. 进入 **Actions** 页面
2. 点击具体的工作流运行记录
3. 点击 **"monitor"** 查看详细日志
4. 日志会显示：
   - 数据读取情况
   - 数据验证结果
   - Apple Store 查询结果
   - 飞书通知发送情况

## 工作流配置

工作流配置文件位于 `.github/workflows/monitor.yml`。

### 默认配置

```yaml
name: Apple App Monitor

on:
  schedule:
    - cron: '0 * * * *'  # 每小时执行一次
  workflow_dispatch:      # 支持手动触发

jobs:
  monitor:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.x'
      - run: pip install -r requirements.txt
      - run: python monitor_apple.py
        env:
          FEISHU_APP_ID: ${{ secrets.FEISHU_APP_ID }}
          FEISHU_APP_SECRET: ${{ secrets.FEISHU_APP_SECRET }}
          FEISHU_WIKI_URL: ${{ secrets.FEISHU_WIKI_URL }}
          FEISHU_CHAT_ID_ALL: ${{ secrets.FEISHU_CHAT_ID_ALL }}
          FEISHU_CHAT_ID_TEAM: ${{ secrets.FEISHU_CHAT_ID_TEAM }}
          FEISHU_MENTION_USERS: ${{ secrets.FEISHU_MENTION_USERS }}
```

### 修改执行频率

编辑 `cron` 表达式：

```yaml
schedule:
  - cron: '0 * * * *'      # 每小时执行
  # - cron: '0 */2 * * *'  # 每 2 小时执行
  # - cron: '0 9-18 * * *' # 每天 9:00-18:00 每小时执行
  # - cron: '0 0 * * *'    # 每天 0:00 执行
  # - cron: '0 0 * * 1'    # 每周一 0:00 执行
```

**注意**：GitHub Actions 使用 UTC 时区，北京时间需要减 8 小时。

### Cron 表达式说明

格式：`分 时 日 月 周`

| 字段 | 允许值 | 说明 |
|------|--------|------|
| 分 | 0-59 | 分钟 |
| 时 | 0-23 | 小时（UTC） |
| 日 | 1-31 | 日期 |
| 月 | 1-12 | 月份 |
| 周 | 0-6 | 星期（0=周日） |

示例：
- `0 * * * *` - 每小时的第 0 分钟
- `30 9 * * *` - 每天 9:30（UTC）
- `0 0 * * 1` - 每周一 0:00（UTC）

## 其他部署方式

### 方式 1：Linux 服务器 + Cron

#### 1. 安装依赖

```bash
pip install -r requirements.txt
```

#### 2. 配置环境变量

编辑 `~/.bashrc` 或 `~/.bash_profile`：

```bash
export FEISHU_APP_ID="your_app_id"
export FEISHU_APP_SECRET="your_app_secret"
export FEISHU_WIKI_URL="your_wiki_url"
export FEISHU_CHAT_ID_ALL="oc_xxx"
export FEISHU_CHAT_ID_TEAM="oc_yyy"
export FEISHU_MENTION_USERS="ou_aaa,ou_bbb"
```

#### 3. 配置 Cron

```bash
crontab -e
```

添加：

```bash
# 每小时执行一次
0 * * * * cd /path/to/apple_monitor && /usr/bin/python3 monitor_apple.py >> /var/log/apple_monitor.log 2>&1
```

### 方式 2：Docker

#### 1. 创建 Dockerfile

```dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "monitor_apple.py"]
```

#### 2. 构建镜像

```bash
docker build -t apple-monitor .
```

#### 3. 运行容器

```bash
docker run -d \
  -e FEISHU_APP_ID="your_app_id" \
  -e FEISHU_APP_SECRET="your_app_secret" \
  -e FEISHU_WIKI_URL="your_wiki_url" \
  -e FEISHU_CHAT_ID_ALL="oc_xxx" \
  -e FEISHU_CHAT_ID_TEAM="oc_yyy" \
  -e FEISHU_MENTION_USERS="ou_aaa,ou_bbb" \
  --name apple-monitor \
  apple-monitor
```

#### 4. 配置定时执行

使用宿主机的 cron 或 Docker 的定时任务功能。

### 方式 3：云函数（Serverless）

#### 腾讯云函数

1. 创建云函数
2. 上传代码包
3. 配置环境变量
4. 设置定时触发器

#### 阿里云函数计算

1. 创建函数
2. 上传代码
3. 配置环境变量
4. 设置时间触发器

## 监控和告警

### GitHub Actions 通知

配置 GitHub Actions 失败通知：

1. 进入仓库 Settings -> Notifications
2. 启用 "Actions" 通知
3. 选择通知方式（Email / Web）

### 自定义告警

在代码中添加告警逻辑：

```python
# monitor_apple.py
if len(invalid_records) > 5:
    # 发送紧急告警
    send_urgent_alert()
```

## 故障排查

### 问题 1：工作流没有自动执行

**可能原因：**
- Actions 未启用
- 仓库不活跃（GitHub 可能暂停定时任务）

**解决方案：**
1. 检查 Actions 是否启用
2. 手动触发一次工作流
3. 确保仓库有活动（提交代码）

### 问题 2：执行失败

**可能原因：**
- Secrets 配置错误
- 飞书权限不足
- 代码错误

**解决方案：**
1. 查看 Actions 日志中的错误信息
2. 检查 Secrets 是否配置正确
3. 本地测试代码

### 问题 3：超时

**可能原因：**
- 数据量太大
- 网络问题

**解决方案：**
1. 优化查询逻辑
2. 增加超时时间
3. 分批处理数据

### 问题 4：重复通知

**可能原因：**
- 状态未正确更新
- 版本号匹配逻辑问题

**解决方案：**
1. 检查表格更新是否成功
2. 查看日志中的版本号比较结果
3. 确认数据验证逻辑

## 成本估算

### GitHub Actions（推荐）

- 免费账户：2000 分钟/月
- 每次执行：约 1-2 分钟
- 每小时执行：24 次/天 × 30 天 = 720 次/月
- 总耗时：720 × 2 = 1440 分钟/月
- **结论：完全免费，够用**

### 云服务器

- 最低配置：1核1G
- 成本：约 ¥50-100/月
- 适合：需要更高频率执行或其他服务

### 云函数

- 按调用次数计费
- 每月有免费额度
- 成本：约 ¥0-10/月
- 适合：低频执行

## 最佳实践

1. **使用 GitHub Actions**：免费、稳定、日志完整
2. **配置告警**：及时发现问题
3. **定期检查日志**：确保正常运行
4. **备份配置**：保存 Secrets 配置
5. **版本控制**：使用 Git 管理代码变更

## 安全建议

1. **不要提交敏感信息**：使用 Secrets 管理密钥
2. **定期更新密钥**：定期轮换 App Secret
3. **最小权限原则**：只授予必要的权限
4. **监控异常访问**：关注飞书应用的访问日志
