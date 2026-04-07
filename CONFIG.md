# 配置说明

本文档详细说明了 Apple 应用监控系统的所有配置项。

## 环境变量配置

### 必需配置

| 变量名 | 说明 | 示例值 |
|--------|------|--------|
| `ENV` | 环境标识 | `local` 或 `production` |
| `FEISHU_APP_ID` | 飞书应用 ID | `cli_a9ccfb2bbf385cc6` |
| `FEISHU_APP_SECRET` | 飞书应用密钥 | `your_secret_here` |
| `FEISHU_WIKI_URL` | 飞书多维表格 Wiki URL | `https://xxx.feishu.cn/wiki/...` |

**ENV 说明：**
- `local`：本地调试模式，不发送飞书通知，适合开发测试
- `production`：生产环境，发送飞书通知，适合正式运行

### 可选配置（飞书通知）

**注意：** 当 `ENV=local` 时，以下配置不生效（不发送通知）

| 变量名 | 说明 | 示例值 |
|--------|------|--------|
| `FEISHU_CHAT_ID_ALL` | @所有人的群聊 ID | `oc_1de66c6e3d6dba470e302b2d474db39f` |
| `FEISHU_CHAT_ID_TEAM` | @指定用户的群聊 ID | `oc_26e985ac87884ce23bc1c181cf0f61dc` |
| `FEISHU_MENTION_USERS` | 要 @ 的用户 ID 列表（逗号分隔） | `ou_aaa,ou_bbb,ou_ccc` |
| `FEISHU_MESSAGE_PREFIX` | 飞书消息统一前缀（可选，空则不加） | `[正式环境]` |

## 配置文件位置

### 本地开发

创建 `.env` 文件在项目根目录：

```bash
# 复制模板
cp .env.example .env
```

编辑 `.env` 文件：

```bash
# 本地调试模式（不发送飞书通知）
ENV=local

# 飞书应用配置
FEISHU_APP_ID=cli_a9ccfb2bbf385cc6
FEISHU_APP_SECRET=your_secret_here
FEISHU_WIKI_URL=https://xxx.feishu.cn/wiki/...

# 本地调试时可以不配置通知
# FEISHU_CHAT_ID_ALL=oc_xxx
# FEISHU_CHAT_ID_TEAM=oc_yyy
# FEISHU_MENTION_USERS=ou_aaa,ou_bbb,ou_ccc
# FEISHU_MESSAGE_PREFIX=[正式环境]
```

### GitHub Actions

在 GitHub 仓库中配置 Secrets：

1. 进入仓库 Settings -> Secrets and variables -> Actions
2. 点击 "New repository secret" 添加密钥

**注意：** GitHub Actions 默认为生产环境（`ENV=production`），会发送飞书通知。

## 配置管理（config/settings.py）

配置类 `Settings` 负责加载和管理所有配置：

```python
from config.settings import settings

# 访问配置
app_id = settings.FEISHU_APP_ID
notifications = settings.FEISHU_NOTIFICATIONS
message_prefix = settings.FEISHU_MESSAGE_PREFIX

# 验证配置
if settings.validate():
    print("配置有效")
```

### 通知配置结构

`FEISHU_NOTIFICATIONS` 是一个列表，每个元素包含：

```python
{
    "chat_id": "oc_xxx",              # 群聊 ID（必需）
    "mention_all": True,              # 是否 @ 所有人（可选）
    "mention_user_ids": ["ou_xxx"]    # 要 @ 的用户列表（可选）
}
```

## 飞书应用配置

### 1. 创建飞书应用

1. 访问 [飞书开放平台](https://open.feishu.cn/)
2. 创建企业自建应用
3. 获取 App ID 和 App Secret

### 2. 配置权限

在应用管理页面添加以下权限：

- `bitable:app` - 查看、编辑多维表格
- `wiki:space` - 访问知识库
- `im:message` - 发送消息

### 3. 添加应用到群聊

1. 打开飞书群聊
2. 点击右上角「...」->「设置」
3. 找到「群机器人」->「添加机器人」
4. 搜索并添加你的应用

### 4. 添加应用为多维表格协作者

1. 打开飞书多维表格
2. 点击右上角「...」->「高级设置」或「协作者」
3. 搜索并添加你的应用
4. 确保权限设置为「可编辑」

## 获取群聊 ID 和用户 ID

### 获取群聊 ID

方法 1：通过群设置
1. 打开飞书群聊
2. 点击右上角「...」->「设置」
3. 在 URL 中可以看到群聊 ID（格式：`oc_xxx`）

方法 2：通过开发者工具
1. 使用飞书 API 获取群列表
2. 查找对应群聊的 `chat_id`

### 获取用户 ID

方法 1：通过用户信息
1. 在飞书中打开用户个人资料
2. 使用飞书 API 查询用户信息

方法 2：通过开发者工具
1. 使用飞书 API 获取部门用户列表
2. 查找对应用户的 `open_id`

## 业务规则配置

当前实现把规则拆成两条独立流程：

1. `App 是否上线` 监控
2. `项目管理记录审查`

核心入口不再是旧的 `get_records_by_status()` 或统一 `validate_data()`，而是：

- `services/feishu_service.py` 的 `get_grouped_records()`：读取视图内记录并构建父子分组
- `monitor_apple.py` 的 `AppleMonitor.evaluate_records()`：把记录拆分为“审查告警”和“上线监控候选”
- `models/record.py` 的规则方法：
  - `resolve_current_submission_record()`
  - `review_parent_snapshot()`
  - `review_current_submission()`
  - `should_monitor_online()`

### 当前规则

**1. 当前发包流水选择**

- 两条流程都只处理“审核中的记录”
- 单记录模式：记录本身 `包状态 = 提审中` 时，记录本身就是当前流水
- 父子模式：父记录快照 `包状态 = 提审中` 时，记录组才进入处理范围
- 在已进入处理范围的父子组里，只在子记录里选择 `包状态 = 提审中` 的记录
- 当存在多条提审中子记录时，按 `提审时间` 倒序、`版本号` 倒序选出当前流水

**2. Apple 上线监控**

- 只对“当前流水”做 Apple 监控
- `阶段 = 五图`：跳过 Apple 上线监控
- 非 `五图`：要求具备 `Apple ID + 版本号`
- 项目管理审查告警不会自动阻断 Apple 监控；只有缺少监控必需字段时才会跳过

**3. 项目管理记录审查**

- 父记录是“应用快照”
- 父记录必须填写最新 `阶段` 和 `包状态`
- 父记录不应填写 `提审时间`
- 父记录快照异常会先告警，再自动同步 `阶段/包状态`，并自动清空父记录 `提审时间`
- 如果父记录是 `提审中`，但没有任何 `提审中` 子记录，会触发审查告警
- 当前流水记录：
  - `五图`：要求有 `提审时间`，不要求 `版本号`
  - 非 `五图`：要求有 `提审时间` 和 `版本号`

### 自定义规则

如需调整规则，优先修改以下方法：

```python
class ApplePackageRecord:
    def resolve_current_submission_record(self):
        """定义如何选出当前要关注的发包流水"""

    def review_parent_snapshot(self, current_record=None):
        """定义父记录（应用快照）的审查规则"""

    def review_current_submission(self):
        """定义当前流水的审查规则"""

    def should_monitor_online(self):
        """定义哪些记录需要进入 Apple 上线监控"""
```

`validate_data()` 和 `get_latest_version()` 目前仅保留为兼容旧调用的包装方法，不建议作为新的扩展入口。

## 日志配置

日志工具在 `utils/logger.py` 中定义，支持：

- GitHub Actions 日志分组
- 不同级别的日志（info, warning, error, success）
- 时间戳自动添加

### 使用日志

```python
from utils.logger import log_info, log_warning, log_error, log_success

log_info("信息日志")
log_warning("警告日志")
log_error("错误日志")
log_success("成功日志")
```

## 高级配置

### 修改父子分组字段

如果表里“父记录”字段改名，可以调整 `get_grouped_records()` 的 `parent_field`：

```python
records = self.feishu_service.get_grouped_records(
    app_token=app_token,
    table_id=table_id,
    view_id=view_id,
    parent_field="父记录",  # 改成你自己的关联字段名
)
```

### 修改当前流水选择规则

编辑 `models/record.py` 中的 `resolve_current_submission_record()`：

```python
return sorted(
    candidates,
    key=lambda record: (
        record.submission_time or 0,
        self._safe_version(record.version),
        record.record_id or "",
    ),
    reverse=True,
)[0]
```

### 修改项目管理审查规则

编辑 `models/record.py` 中的 `review_parent_snapshot()` 和 `review_current_submission()`：

```python
def review_parent_snapshot(self, current_record=None):
    errors = []

    if self.submission_time:
        errors.append("父记录不应填写提审时间")
    if not self.package_status:
        errors.append("父记录缺少包状态")
    if current_record and self.package_status != current_record.package_status:
        errors.append("父记录包状态未同步最新状态")

    return {"is_valid": len(errors) == 0, "errors": errors}
```

### 修改 Apple 监控条件

如果要调整哪些记录进入 Apple 监控，优先改两个位置：

```python
def should_monitor_online(self):
    return self.stage != "五图"
```

```python
apple_id = current_record.resolve_monitor_apple_id(record)
if not apple_id:
    online_errors.append("缺少 Apple ID，无法监控上线")
if not current_record.version:
    online_errors.append("缺少版本号，无法监控上线")
```

## 故障排查

### 配置验证失败

运行以下命令检查配置：

```python
from config.settings import settings

if settings.validate():
    print("✅ 配置有效")
    print(f"App ID: {settings.FEISHU_APP_ID}")
    print(f"通知配置: {len(settings.FEISHU_NOTIFICATIONS)} 个群")
else:
    print("❌ 配置无效，请检查环境变量")
```

### 权限问题

如果遇到权限错误，检查：

1. 飞书开放平台是否已添加所需权限
2. 应用是否已添加到目标群聊
3. 应用是否已添加为多维表格协作者

### 环境变量未生效

确保：

1. `.env` 文件在项目根目录
2. 环境变量名称正确（区分大小写）
3. 重启应用以加载新的环境变量
