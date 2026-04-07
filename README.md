# Apple 应用监控系统

自动监控 Apple Store 应用上线状态，并对飞书表格中的项目管理记录做顺带审查。

## 功能特性

- 🔍 自动查询 Apple Store 应用状态
- 📊 从飞书多维表格读取应用信息
- ✅ 区分“上线监控”和“项目管理记录审查”两条流程
- � 应用上线后自动发送飞书通知（支持 @ 所有人或指定用用户）
- ⚠️ 项目管理记录审查自动预警
- ⏰ 支持定时执行（GitHub Actions）
- 📝 自动更新飞书表格状态

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env` 并填写配置：

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```bash
# 环境配置
ENV=local  # 本地调试模式（不发送飞书通知）

# 飞书应用配置（必需）
FEISHU_APP_ID=your_app_id
FEISHU_APP_SECRET=your_app_secret
FEISHU_WIKI_URL=your_wiki_url

# 飞书通知配置（生产环境需要，本地调试可不填）
# FEISHU_CHAT_ID_ALL=oc_xxx
# FEISHU_CHAT_ID_TEAM=oc_yyy
# FEISHU_MENTION_USERS=ou_aaa,ou_bbb
# FEISHU_MESSAGE_PREFIX=[正式环境]
```

`FEISHU_MESSAGE_PREFIX` 是可选项；为空或不配置时，飞书消息不加前缀。

**环境说明：**
- `ENV=local`：本地调试模式，不发送飞书通知
- `ENV=production`：生产环境，发送飞书通知

### 3. 运行脚本

```bash
python monitor_apple.py
```

## 配置说明

详细配置说明请查看 [CONFIG.md](CONFIG.md)

## 部署指南

GitHub Actions 部署指南请查看 [DEPLOY.md](DEPLOY.md)

## 项目结构

```
apple_monitor/
├── config/                    # 配置管理
│   ├── __init__.py
│   └── settings.py           # 环境变量配置
├── models/                    # 数据模型
│   ├── __init__.py
│   └── record.py             # ApplePackageRecord 数据模型
├── services/                  # 外部服务
│   ├── __init__.py
│   ├── apple_service.py      # Apple Store API 服务
│   ├── feishu_service.py     # 飞书表格服务
│   └── feishu_messenger.py   # 飞书消息服务
├── utils/                     # 工具函数
│   ├── __init__.py
│   ├── logger.py             # 日志工具
│   └── url_parser.py         # URL 解析工具
├── monitor_apple.py          # 主入口（业务流程编排）
├── requirements.txt          # 依赖包
├── .env                      # 环境变量配置
├── CONFIG.md                 # 配置文档
└── DEPLOY.md                 # 部署文档
```

## 业务规则

系统会把“App 是否上线”和“项目管理记录审查”分成两条独立流程。

### 1. App 上线监控

- 两条流程都只针对“审核中的记录”
- 单记录模式：记录本身 `包状态 = 提审中` 时，记录本身是监控对象
- 父子模式：父记录快照 `包状态 = 提审中` 时，才会继续处理该记录组
- 在已进入处理范围的父子组里，从 `包状态 = 提审中` 的子记录里，按 `提审时间` 最近、`版本号` 最大选出当前流水
- `阶段 = 五图`：不做 Apple 上线监控
- 非 `五图`：要求当前流水具备 `Apple ID + 版本号`

### 2. 项目管理记录审查

- 同样只审查“审核中的记录”
- 父记录：只审查快照字段
- 父记录必须填写最新 `阶段` 和 `包状态`
- 父记录不应填写 `提审时间`
- 父记录快照异常会先告警，再自动同步 `阶段/包状态`，并自动清空父记录 `提审时间`
- 如果父记录是 `提审中`，但没有任何 `提审中` 子记录，会触发审查告警
- 当前流水记录：
  - `五图`：要求有 `提审时间`，不要求 `版本号`
  - 非 `五图`：要求有 `提审时间` 和 `版本号`

项目管理审查告警不会自动阻断 Apple 上线监控；只有缺少 `Apple ID` 或 `版本号` 这类上线监控必需字段时，才会跳过对应监控项。

## 权限要求

飞书应用需要以下权限：

- ✅ `bitable:app` - 查看、编辑多维表格
- ✅ `wiki:space` - 访问知识库
- ✅ `im:message` - 发送消息

## 本地开发

### 环境要求

- Python 3.7+
- pip

### 开发流程

1. 克隆仓库
2. 安装依赖：`pip install -r requirements.txt`
3. 配置 `.env` 文件
4. 运行脚本：`python monitor_apple.py`

## 故障排查

### 问题：项目管理记录审查告警

查看日志中的审查问题详情，会显示父记录或当前流水记录的具体问题。

### 问题：飞书消息发送失败

- 检查应用是否已添加到目标群聊
- 检查应用是否有 `im:message` 权限
- 查看错误码和错误信息

### 问题：表格更新失败

- 检查应用是否有 `bitable:app` 权限
- 检查应用是否已添加为多维表格的协作者

## License

MIT
