"""
飞书多维表格监控脚本
读取多维表格并筛选出"包状态"为"提审中"的记录
"""
import lark_oapi as lark
from lark_oapi.api.bitable.v1 import ListAppTableRecordRequest, ListAppTableRequest, UpdateAppTableRecordRequest
from lark_oapi.api.bitable.v1.model import AppTableRecord
from lark_oapi.api.wiki.v2.model.get_node_space_request import GetNodeSpaceRequest
from lark_oapi.api.im.v1 import CreateMessageRequest, CreateMessageRequestBody
from typing import List, Dict, Any, Optional, Tuple
from model import ApplePackageRecord
import requests
import json
import uuid
import os
from datetime import datetime


# ============================================
# GitHub Actions 日志辅助函数
# ============================================

def is_github_actions() -> bool:
    """检查是否在 GitHub Actions 环境中运行"""
    return os.getenv('GITHUB_ACTIONS') == 'true'


def log_group(title: str):
    """开始一个可折叠的日志组"""
    if is_github_actions():
        print(f"::group::{title}")
    else:
        print(f"\n{'='*60}")
        print(f"{title}")
        print(f"{'='*60}")


def log_endgroup():
    """结束日志组"""
    if is_github_actions():
        print("::endgroup::")


def log_info(message: str):
    """输出信息日志"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    if is_github_actions():
        print(f"[{timestamp}] {message}")
    else:
        print(f"[{timestamp}] {message}")


def log_warning(message: str):
    """输出警告日志"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    if is_github_actions():
        print(f"::warning::{message}")
    print(f"[{timestamp}] ⚠️  {message}")


def log_error(message: str):
    """输出错误日志"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    if is_github_actions():
        print(f"::error::{message}")
    print(f"[{timestamp}] ❌ {message}")


def log_success(message: str):
    """输出成功日志"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    if is_github_actions():
        print(f"::notice::{message}")
    print(f"[{timestamp}] ✅ {message}")


class FeishuBitableMonitor:
    """飞书多维表格监控类"""
    
    def __init__(self, app_id: str, app_secret: str, user_access_token: Optional[str] = None):
        """
        初始化飞书客户端
        
        Args:
            app_id: 飞书应用的 App ID
            app_secret: 飞书应用的 App Secret
            user_access_token: 用户访问令牌（可选，用于需要用户权限的操作）
        """
        self.app_id = app_id
        self.app_secret = app_secret
        self.user_access_token = user_access_token
        self.client = lark.Client.builder() \
            .app_id(app_id) \
            .app_secret(app_secret) \
            .log_level(lark.LogLevel.INFO) \
            .build()
    
    def get_app_token_from_wiki(self, wiki_node_token: str) -> Optional[str]:
        """
        从知识库（wiki）节点获取多维表格的 app_token
        
        Args:
            wiki_node_token: 知识库节点的 token（从 wiki URL 中提取）
        
        Returns:
            多维表格的 app_token（即 obj_token），如果失败返回 None
        """
        log_info(f"🔍 从知识库节点获取 app_token，节点 token: {wiki_node_token}")
        try:
            request = GetNodeSpaceRequest.builder() \
                .token(wiki_node_token) \
                .build()
            
            response = self.client.wiki.v2.space.get_node(request)
            
            if response.success():
                node = response.data.node
                obj_type = node.obj_type
                obj_token = node.obj_token
                
                log_success("成功获取节点信息")
                log_info(f"  - 节点类型: {obj_type}")
                log_info(f"  - obj_token (app_token): {obj_token}")
                
                if obj_type == "bitable":
                    log_success("确认是多维表格节点")
                    return obj_token
                else:
                    log_warning(f"节点类型不是多维表格 (bitable)，而是: {obj_type}")
                    return None
            else:
                log_error(f"获取节点信息失败: {response.code}, {response.msg}")
                log_info("\n可能的原因：")
                log_info("1. wiki_node_token 不正确")
                log_info("2. 应用没有访问该知识库节点的权限")
                log_info("3. 节点不存在或已被删除")
                return None
        except Exception as e:
            log_error(f"获取节点信息异常: {str(e)}")
            return None
    
    def check_app_permissions(self) -> None:
        """
        检查应用当前拥有的权限范围
        """
        log_info("🔍 检查应用权限...")
        log_info(f"  App ID: {self.app_id}")
        
        # 尝试获取 tenant_access_token 来查看权限
        try:
            # 这里我们通过尝试不同的 API 来推断权限
            log_info("  已配置的权限应该包括：")
            log_info("  - bitable:app (查看、编辑多维表格)")
            log_info("  - wiki:space (访问知识库)")
            log_info("  💡 请在飞书开放平台确认这些权限已添加并生效")
            log_info(f"     https://open.feishu.cn/app/{self.app_id}/permission")
            
        except Exception as e:
            log_error(f"检查异常: {str(e)}")
    
    def test_connection(self, app_token: str) -> bool:
        """
        测试连接，验证 app_token 是否正确
        
        Args:
            app_token: 多维表格的应用 Token
        
        Returns:
            连接是否成功
        """
        try:
            request = ListAppTableRequest.builder() \
                .app_token(app_token) \
                .build()
            
            response = self.client.bitable.v1.app_table.list(request)
            
            if response.success():
                tables = response.data.items
                log_success(f"连接成功！找到 {len(tables)} 个表格")
                log_info("可用的表格列表：")
                for table in tables:
                    log_info(f"  - 表格名称: {table.name}")
                    log_info(f"    表格 ID: {table.table_id}")
                return True
            else:
                log_error(f"连接失败: {response.code}, {response.msg}")
                return False
        except Exception as e:
            log_error(f"连接异常: {str(e)}")
            return False
    
    
    def get_all_records(
        self,
        app_token: str,
        table_id: str,
        view_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        获取所有记录（用于后续筛选）
        
        Args:
            app_token: 多维表格的应用 Token
            table_id: 表格 ID
            view_id: 视图 ID（可选）
        
        Returns:
            所有记录的列表（包含 record_id 和 fields）
        """
        all_records = []
        page_token = None
        
        while True:
            request_builder = ListAppTableRecordRequest.builder() \
                .app_token(app_token) \
                .table_id(table_id) \
                .page_size(500)
            
            if view_id:
                request_builder.view_id(view_id)
            
            if page_token:
                request_builder.page_token(page_token)
            
            request = request_builder.build()
            response = self.client.bitable.v1.app_table_record.list(request)
            
            if not response.success():
                log_error(f"请求失败: {response.code}, {response.msg}")
                break
            
            items = response.data.items
            if not items:
                break
            
            for record in items:
                if record.fields:
                    all_records.append({
                        'record_id': record.record_id,
                        'fields': record.fields
                    })
            
            if not response.data.has_more:
                break
            
            page_token = response.data.page_token
        
        return all_records
    
    def get_records_by_status(
        self, 
        app_token: str, 
        table_id: str, 
        status_field: str = "包状态",
        target_status: str = "提审中",
        view_id: Optional[str] = None,
        parent_field: str = "父记录"
    ) -> List[ApplePackageRecord]:
        """
        获取指定状态的主应用记录及其所有子记录（版本记录）
        
        查询逻辑：
        1. 查找所有父记录为空且包状态=提审中的记录（主应用）
        2. 查找这些主应用的所有子记录（版本记录）
        
        Args:
            app_token: 多维表格的应用 Token
            table_id: 表格 ID
            status_field: 状态字段名称，默认为"包状态"
            target_status: 目标状态值，默认为"提审中"
            view_id: 视图 ID（可选），如果提供则只读取该视图下的数据
            parent_field: 父记录字段名称，默认为"父记录"
        
        Returns:
            主应用记录列表（每个记录包含其子记录）
        """
        log_info("开始读取多维表格，查询逻辑：")
        log_info(f"  步骤1: 查找父记录为空且{status_field} = {target_status}的记录（主应用）")
        log_info(f"  步骤2: 查找步骤1中所有主应用的子记录（版本记录）")
        log_info(f"  table_id: {table_id}")
        if view_id:
            log_info(f"  view_id: {view_id} (指定视图)")
        
        # 步骤1: 获取所有记录
        log_info("步骤1: 获取所有记录...")
        all_raw_records = self.get_all_records(app_token, table_id, view_id)
        log_info(f"  共获取 {len(all_raw_records)} 条记录")
        
        # 步骤2: 筛选父记录为空且包状态=提审中的主应用记录
        log_info("步骤2: 筛选主应用记录（父记录为空且包状态=提审中）...")
        main_apps: List[ApplePackageRecord] = []
        main_app_record_ids = set()
        
        for raw_record in all_raw_records:
            fields = raw_record['fields']
            if not fields:
                continue
            
            # 检查包状态
            status_match = False
            if status_field in fields:
                status_value = fields[status_field]
                if isinstance(status_value, list):
                    status_text = [str(item) for item in status_value]
                    status_match = target_status in status_text
                else:
                    status_match = str(status_value) == target_status
            
            if not status_match:
                continue
            
            # 检查父记录是否为空
            parent_empty = False
            if parent_field not in fields:
                parent_empty = True
            else:
                parent_value = fields[parent_field]
                if isinstance(parent_value, list):
                    if len(parent_value) == 0:
                        parent_empty = True
                    else:
                        is_empty = True
                        for item in parent_value:
                            if isinstance(item, dict):
                                if 'record_ids' in item and item.get('record_ids'):
                                    is_empty = False
                                    break
                                if 'text' in item and item.get('text'):
                                    is_empty = False
                                    break
                        parent_empty = is_empty
                elif parent_value is None or parent_value == "":
                    parent_empty = True
            
            if status_match and parent_empty:
                package_record = ApplePackageRecord.from_feishu_fields(
                    fields=fields,
                    record_id=raw_record['record_id']
                )
                main_apps.append(package_record)
                main_app_record_ids.add(raw_record['record_id'])
        
        log_info(f"  找到 {len(main_apps)} 个主应用")
        
        # 步骤3: 查找每个主应用的所有子记录（版本记录）
        # 只包含状态为"提审中"或"已发布"的子记录
        log_info("步骤3: 查找每个主应用的子记录（版本记录）...")
        log_info("  子记录过滤条件: 包状态 = '提审中' 或 '已发布'")
        valid_child_statuses = ["提审中", "已发布"]
        
        for main_app in main_apps:
            children = []
            for raw_record in all_raw_records:
                fields = raw_record['fields']
                if not fields or parent_field not in fields:
                    continue
                
                # 检查该记录是否指向当前主应用
                parent_value = fields[parent_field]
                if isinstance(parent_value, list):
                    for item in parent_value:
                        if isinstance(item, dict):
                            record_ids = item.get('record_ids', [])
                            # 确保 record_ids 不为 None
                            if record_ids and main_app.record_id in record_ids:
                                # 这是当前主应用的子记录，检查状态
                                child_status = None
                                if status_field in fields:
                                    status_value = fields[status_field]
                                    if isinstance(status_value, list):
                                        child_status = [str(item) for item in status_value]
                                    else:
                                        child_status = str(status_value)
                                
                                # 只添加状态为"提审中"或"已发布"的子记录
                                status_valid = False
                                if isinstance(child_status, list):
                                    status_valid = any(s in valid_child_statuses for s in child_status)
                                elif child_status:
                                    status_valid = child_status in valid_child_statuses
                                
                                if status_valid:
                                    child_record = ApplePackageRecord.from_feishu_fields(
                                        fields=fields,
                                        record_id=raw_record['record_id']
                                    )
                                    children.append(child_record)
                                break
            
            main_app.children = children
            log_info(f"  主应用 {main_app.package_name} (ID: {main_app.record_id}) 有 {len(children)} 条有效版本记录")
        
        log_success(f"查询完成，共找到 {len(main_apps)} 个主应用及其版本记录")
        return main_apps
    
    def query_apple_app_status(self, apple_id: int, verbose: bool = False) -> Optional[Dict[str, Any]]:
        """
        使用 Apple Lookup API (iTunes Search API) 查询应用状态
        
        Args:
            apple_id: Apple 应用 ID
            verbose: 是否打印详细信息
        
        Returns:
            应用信息字典，包含：
            - is_online: 是否已上线
            - version: 当前版本号
            - track_name: 应用名称
            - release_date: 发布日期
            - current_version_release_date: 当前版本发布日期
            如果查询失败返回 None
        """
        url = f"https://itunes.apple.com/lookup"
        params = {
            'id': apple_id,
            'country': 'us'
        }
        
        try:
            if verbose:
                log_info(f"🔍 查询 Apple 应用状态，Apple ID: {apple_id}")
                log_info(f"  API URL: {url}")
                log_info(f"  参数: {params}")
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('resultCount', 0) == 0:
                if verbose:
                    log_warning(f"未找到应用信息（Apple ID: {apple_id}）")
                return {
                    'is_online': False,
                    'version': None,
                    'track_name': None,
                    'release_date': None,
                    'current_version_release_date': None
                }
            
            result = data['results'][0]
            
            app_info = {
                'is_online': True,
                'version': result.get('version'),
                'track_name': result.get('trackName'),
                'release_date': result.get('releaseDate'),
                'current_version_release_date': result.get('currentVersionReleaseDate'),
                'bundle_id': result.get('bundleId'),
                'track_view_url': result.get('trackViewUrl')
            }
            
            if verbose:
                log_success("查询成功")
                log_info(f"  应用名称: {app_info['track_name']}")
                log_info(f"  版本号: {app_info['version']}")
                log_info(f"  是否上线: 是")
                log_info(f"  发布日期: {app_info['release_date']}")
                log_info(f"  当前版本发布日期: {app_info['current_version_release_date']}")
                log_info("\n  完整信息:")
                log_info(json.dumps(result, indent=2, ensure_ascii=False))
            
            return app_info
            
        except requests.exceptions.RequestException as e:
            
            log_error(f"请求失败: {str(e)}")
            return None
        except json.JSONDecodeError as e:
            log_error(f"JSON 解析失败: {str(e)}")
            return None
        except Exception as e:
            log_error(f"查询异常: {str(e)}")
            return None
    
    def update_record_fields(
        self,
        app_token: str,
        table_id: str,
        record_id: str,
        fields: Dict[str, Any]
    ) -> bool:
        """
        更新飞书表格中记录的字段
        
        Args:
            app_token: 多维表格的应用 Token
            table_id: 表格 ID
            record_id: 记录 ID
            fields: 要更新的字段字典，例如 {"包状态": "已发布", "过审时间": "2025/12/22"}
        
        Returns:
            更新是否成功
        """
        try:
            # 构建请求
            request = UpdateAppTableRecordRequest.builder() \
                .app_token(app_token) \
                .table_id(table_id) \
                .record_id(record_id) \
                .request_body(
                    AppTableRecord.builder()
                    .fields(fields)
                    .build()
                ) \
                .build()
            
            # 发起请求
            response = self.client.bitable.v1.app_table_record.update(request)
            
            if response.success():
                # 格式化更新信息
                update_info = ", ".join([f"{k}={v}" for k, v in fields.items()])
                log_success(f"更新成功: Record ID {record_id} ({update_info})")
                return True
            else:
                log_error(f"更新失败: Record ID {record_id}")
                log_info(f"  错误码: {response.code}")
                log_info(f"  错误信息: {response.msg}")
                
                return False
                
        except Exception as e:
            log_error(f"更新异常: Record ID {record_id}, 错误: {str(e)}")
            return False
    
    def send_feishu_message(
        self,
        chat_id: str,
        app_name: str,
        stage: str,
        version: str,
        mention_all: bool = False,
        mention_user_ids: Optional[List[str]] = None
    ) -> bool:
        """
        发送消息到飞书群聊
        
        Args:
            chat_id: 飞书群聊 ID
            app_name: 应用名称
            stage: 阶段
            version: 版本号
            mention_all: 是否 @ 所有人
            mention_user_ids: 要 @ 的用户 open_id 列表（可选）
        
        Returns:
            发送是否成功
        """
        if not chat_id:
            log_warning("飞书群聊 ID 未配置，跳过发送消息")
            return False
        
        try:
            message_text = f"{app_name} {stage} V{version} 过审并发布了"
            
            # 构建富文本消息内容（支持 @ 功能）
            content_parts = []
            
            # 添加 @ 所有人
            if mention_all:
                content_parts.append({
                    "tag": "at",
                    "user_id": "all"
                })
                content_parts.append({
                    "tag": "text",
                    "text": " "
                })
            
            # 添加 @ 多个用户
            if mention_user_ids:
                for user_id in mention_user_ids:
                    content_parts.append({
                        "tag": "at",
                        "user_id": user_id
                    })
                    content_parts.append({
                        "tag": "text",
                        "text": " "
                    })
            
            # 添加消息正文
            content_parts.append({
                "tag": "text",
                "text": message_text
            })
            
            # 构建消息内容
            content = json.dumps({
                "zh_cn": {
                    "title": "",
                    "content": [content_parts]
                }
            }, ensure_ascii=False)
            
            # 生成唯一的 UUID
            message_uuid = str(uuid.uuid4())
            
            # 构建请求
            request = CreateMessageRequest.builder() \
                .receive_id_type("chat_id") \
                .request_body(
                    CreateMessageRequestBody.builder()
                    .receive_id(chat_id)
                    .msg_type("post")  # 使用富文本消息类型
                    .content(content)
                    .uuid(message_uuid)
                    .build()
                ) \
                .build()
            
            # 发送消息
            response = self.client.im.v1.message.create(request)
            
            if response.success():
                mention_info = ""
                if mention_all:
                    mention_info = " (@所有人)"
                elif mention_user_ids:
                    mention_info = f" (@{len(mention_user_ids)}人)"
                log_success(f"飞书消息发送成功{mention_info}: {message_text}")
                return True
            else:
                log_error("飞书消息发送失败")
                log_info(f"  错误码: {response.code}")
                log_info(f"  错误信息: {response.msg}")
                if response.code == 230002:
                    log_error("  💡 机器人不在该群聊中，请先将应用添加到群聊")
                    log_info("     - 打开飞书群聊")
                    log_info("     - 点击右上角「...」->「设置」")
                    log_info("     - 找到「群机器人」->「添加机器人」")
                    log_info("     - 搜索并添加你的应用")
                return False
                
        except Exception as e:
            log_error(f"发送飞书消息异常: {str(e)}")
            return False
    
    def send_notifications(
        self,
        notifications: List[Dict[str, Any]],
        app_name: str,
        stage: str,
        version: str
    ) -> None:
        """
        发送通知到多个飞书群聊
        
        Args:
            notifications: 通知配置列表，每个配置包含：
                - chat_id: 群聊 ID
                - mention_all: 是否 @ 所有人（可选）
                - mention_user_ids: 要 @ 的用户 open_id 列表（可选）
            app_name: 应用名称
            stage: 阶段
            version: 版本号
        
        示例：
            notifications = [
                {"chat_id": "oc_xxx", "mention_all": True},
                {"chat_id": "oc_yyy", "mention_user_ids": ["ou_xxx", "ou_yyy"]}
            ]
        """
        if not notifications:
            log_warning("未配置飞书通知，跳过发送")
            return
        
        log_info(f"📨 发送飞书通知到 {len(notifications)} 个群聊...")
        for config in notifications:
            chat_id = config.get("chat_id")
            mention_all = config.get("mention_all", False)
            mention_user_ids = config.get("mention_user_ids")
            
            if not chat_id:
                log_warning("通知配置缺少 chat_id，跳过")
                continue
            
            self.send_feishu_message(
                chat_id=chat_id,
                app_name=app_name,
                stage=stage,
                version=version,
                mention_all=mention_all,
                mention_user_ids=mention_user_ids
            )
    def send_warning_message(
        self,
        chat_id: str,
        invalid_records: List[Tuple[ApplePackageRecord, List[str]]]
    ) -> bool:
        """
        发送数据异常警告消息到飞书群聊

        Args:
            chat_id: 飞书群聊 ID
            invalid_records: 异常记录列表，每个元素是 (record, errors) 元组

        Returns:
            发送是否成功
        """
        if not chat_id or not invalid_records:
            return False

        try:
            # 构建警告消息内容
            warning_lines = [
                "⚠️ 数据异常警告",
                "",
                f"发现 {len(invalid_records)} 个应用存在数据问题，请及时修正：",
                ""
            ]

            for idx, (record, errors) in enumerate(invalid_records, 1):
                warning_lines.append(f"{idx}. {record.package_name}")
                for error in errors:
                    warning_lines.append(f"   - {error}")
                if record.record_id:
                    warning_lines.append(f"   - 记录ID: {record.record_id}")
                warning_lines.append("")

            warning_lines.append("请相关研发人员检查并补充完整信息。")

            message_text = "\n".join(warning_lines)

            # 构建富文本消息内容（@ 所有人）
            content_parts = [
                {
                    "tag": "at",
                    "user_id": "all"
                },
                {
                    "tag": "text",
                    "text": " \n" + message_text
                }
            ]

            # 构建消息内容
            content = json.dumps({
                "zh_cn": {
                    "title": "",
                    "content": [content_parts]
                }
            }, ensure_ascii=False)

            # 生成唯一的 UUID
            message_uuid = str(uuid.uuid4())

            # 构建请求
            request = CreateMessageRequest.builder() \
                .receive_id_type("chat_id") \
                .request_body(
                    CreateMessageRequestBody.builder()
                    .receive_id(chat_id)
                    .msg_type("post")
                    .content(content)
                    .uuid(message_uuid)
                    .build()
                ) \
                .build()

            # 发送消息
            response = self.client.im.v1.message.create(request)

            if response.success():
                log_success(f"数据异常警告发送成功 (@所有人)")
                return True
            else:
                log_error("数据异常警告发送失败")
                log_info(f"  错误码: {response.code}")
                log_info(f"  错误信息: {response.msg}")
                return False

        except Exception as e:
            log_error(f"发送数据异常警告异常: {str(e)}")
            return False

    
    def update_app_status(
        self,
        app_token: str,
        table_id: str,
        record: ApplePackageRecord,
        latest_version: str,
        current_date_timestamp: int
    ) -> None:
        """
        更新应用的飞书表格状态
        
        Args:
            app_token: 多维表格的应用 Token
            table_id: 表格 ID
            record: 应用记录
            latest_version: 最新版本号
            current_date_timestamp: 当前日期的时间戳（毫秒）
        """
        log_info("📝 更新飞书表格状态...")

        # 要更新的字段
        update_child_fields = {
            "包状态": "已发布",
            "过审时间": current_date_timestamp  # 使用时间戳（毫秒）
        }


        # 更新主记录的字段
        update_fields = {
            "包状态": "已发布",
        }    
        
        if record.children:
            # 有子记录：找到对应版本号的子记录并更新
            target_child = None
            for child in record.children:
                if child.version == latest_version:
                    target_child = child
                    break
            
            if target_child:
                # 更新子记录状态
                log_info(f"  更新子记录: {target_child.record_id} (版本: {target_child.version})")
                self.update_record_fields(
                    app_token=app_token,
                    table_id=table_id,
                    record_id=target_child.record_id,
                    fields=update_child_fields
                )
        else:        
            # 如果没有子记录, 那么当前记录只有一条记录，则记录过审时间
            update_fields = {
                "包状态": "已发布",
                "过审时间": current_date_timestamp 
            } 

        

        # 没有子记录：只更新主记录, 只更新状态，不更新时间
        log_info(f"  更新主记录: {record.record_id}")
        self.update_record_fields(
            app_token=app_token,
            table_id=table_id,
            record_id=record.record_id,
            fields=update_fields
        )
            
    
    def print_records(self, records: List[ApplePackageRecord]):
        """
        打印记录信息（包括主应用和其版本记录）
        
        Args:
            records: 主应用记录列表（ApplePackageRecord 对象，包含子记录）
        """
        print(f"\n{'='*60}")
        print(f"找到 {len(records)} 个主应用")
        total_versions = sum(len(app.children) for app in records)
        print(f"共 {total_versions} 条版本记录")
        print(f"{'='*60}\n")
        
        for idx, main_app in enumerate(records, 1):
            print(f"{'='*60}")
            print(f"主应用 #{idx}: {main_app.package_name}")
            print(f"{'='*60}")
            print(f"  Record ID: {main_app.record_id}")
            print(f"  应用: {main_app.package_name}")
            print(f"  阶段: {main_app.stage}")
            print(f"  包状态: {main_app.package_status}")
            print(f"  Apple ID: {main_app.apple_id}")
            print(f"  版本号: {main_app.version}")
            latest_version = main_app.get_latest_version()
            print(f"  最新版本: {latest_version}")
            print(f"  团队: {main_app.team}")
            print(f"  所属季度: {main_app.quarter}")
            if main_app.developers:
                dev_names = [dev.name for dev in main_app.developers if hasattr(dev, 'name')]
                print(f"  开发人员: {', '.join(dev_names) if dev_names else 'N/A'}")
            if main_app.submission_time:
                dt = datetime.fromtimestamp(main_app.submission_time / 1000)
                print(f"  提审时间: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
            
            # 打印子记录（版本记录）
            if main_app.children:
                print(f"\n  └─ 版本记录（共 {len(main_app.children)} 条）:")
                for child_idx, child in enumerate(main_app.children, 1):
                    print(f"     [{child_idx}] 版本: {child.version} | 状态: {child.package_status} | Record ID: {child.record_id}")
                    if child.submission_time:
                        dt = datetime.fromtimestamp(child.submission_time / 1000)
                        print(f"         提审时间: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
            else:
                print(f"\n  └─ 无版本记录")
            print()


def parse_wiki_url(url: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    解析 wiki URL，提取节点 token、table_id 和 view_id
    
    Args:
        url: wiki URL
    
    Returns:
        (wiki_node_token, table_id, view_id) 元组
    """
    try:
        # 从 URL 中提取 wiki 节点 token
        # 格式: https://xxx.feishu.cn/wiki/NODE_TOKEN?table=TABLE_ID&view=VIEW_ID
        if "/wiki/" in url:
            parts = url.split("/wiki/")[1].split("?")[0]
            wiki_node_token = parts
            
            # 提取 table_id 和 view_id
            table_id = None
            view_id = None
            if "?" in url:
                params = url.split("?")[1]
                for param in params.split("&"):
                    if param.startswith("table="):
                        table_id = param.split("=")[1]
                    elif param.startswith("view="):
                        view_id = param.split("=")[1]
            
            return wiki_node_token, table_id, view_id
    except Exception as e:
        log_error(f"解析 URL 失败: {str(e)}")
    
    return None, None, None


def main():
    """主函数"""
    # 打印任务开始信息
    log_group("🚀 Apple 应用监控任务开始")
    log_info(f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log_info(f"运行环境: {'GitHub Actions' if is_github_actions() else 'Local'}")
    log_endgroup()
    
    # 配置信息（从环境变量读取）
    APP_ID = os.getenv("FEISHU_APP_ID")
    APP_SECRET = os.getenv("FEISHU_APP_SECRET")
    WIKI_URL = os.getenv("FEISHU_WIKI_URL")

    if not APP_ID or not APP_SECRET or not WIKI_URL:
        log_error("缺少必要的环境变量")
        log_info("请设置以下环境变量：")
        log_info("  - FEISHU_APP_ID")
        log_info("  - FEISHU_APP_SECRET")
        log_info("  - FEISHU_WIKI_URL")
        return []
    
    # 创建监控实例
    monitor = FeishuBitableMonitor(APP_ID, APP_SECRET)
    
    # 解析 wiki URL
    log_group("📋 步骤 0: 解析 Wiki URL")
    wiki_node_token, table_id, view_id = parse_wiki_url(WIKI_URL)
    
    if not wiki_node_token:
        log_error("无法从 URL 中提取 wiki 节点 token")
        log_endgroup()
        return []
    
    log_success("解析成功")
    log_info(f"Wiki 节点 token: {wiki_node_token}")
    log_info(f"Table ID: {table_id}")
    log_info(f"View ID: {view_id}")
    log_endgroup()
    
    # 从 wiki 节点获取 app_token
    log_group("🔑 步骤 1: 从知识库节点获取 app_token")
    app_token = monitor.get_app_token_from_wiki(wiki_node_token)
    
    if not app_token:
        log_error("无法获取 app_token")
        log_info("   请检查：")
        log_info("   1. 应用是否有访问知识库的权限")
        log_info("   2. wiki_node_token 是否正确")
        log_info("   3. 节点是否是多维表格类型")
        log_endgroup()
        return []
    log_endgroup()
    
    # 测试连接，验证 app_token 是否正确
    log_group("🔌 步骤 2: 测试连接")
    if not monitor.test_connection(app_token):
        log_error("连接失败，请检查 app_token 是否正确")
        log_endgroup()
        return []
    log_endgroup()
    
    log_group("📊 步骤 3: 读取并筛选数据")
    
    # 获取"包状态"为"提审中"的记录
    if not table_id:
        log_error("未找到 table_id，无法继续")
        log_endgroup()
        return []
    
    records = monitor.get_records_by_status(
        app_token=app_token,
        table_id=table_id,
        status_field="包状态",
        target_status="提审中",
        view_id=view_id  # 传入视图 ID，从指定视图读取数据
    )
    log_endgroup()
    
    # 过滤出阶段 != "五图" 的所有记录
    log_group("🔍 步骤 4: 过滤阶段 != '五图' 的记录")
    filtered_records = []
    for record in records:
        if record.stage != "五图":
            filtered_records.append(record)
        else:
            log_info(f"过滤掉: {record.package_name} (阶段: {record.stage})")
    
    log_info(f"过滤前: {len(records)} 个主应用")
    log_info(f"过滤后: {len(filtered_records)} 个主应用（阶段 != '五图'）")
    log_endgroup()
    
    # 数据验证：分离有效记录和异常记录
    log_group("📦 步骤 5: 数据验证")
    valid_records = []
    invalid_records = []
    
    for record in filtered_records:
        validation_result = record.validate_data()
        
        if validation_result['is_valid']:
            valid_records.append(record)
            latest_version = record.get_latest_version()
            
            # 调试信息：打印子记录详情
            if record.children:
                log_info(f"✅ {record.package_name}: 最新版本 = {latest_version} (来自子记录)")
                log_info(f"  父记录版本: {record.version}")
                log_info(f"  子记录数量: {len(record.children)}")
                for idx, child in enumerate(record.children, 1):
                    log_info(f"    子记录{idx}: 版本={child.version}, 提审时间={child.submission_time}")
            else:
                log_info(f"✅ {record.package_name}: 最新版本 = {latest_version} (主记录)")
        else:
            invalid_records.append((record, validation_result['errors']))
            log_warning(f"❌ {record.package_name}: 数据异常")
            for error in validation_result['errors']:
                log_warning(f"  - {error}")
    
    log_info(f"\n数据验证结果：")
    log_info(f"  有效记录: {len(valid_records)} 个")
    log_info(f"  异常记录: {len(invalid_records)} 个")
    
    # 打印异常记录详细信息
    if invalid_records:
        log_info(f"\n异常记录详情：")
        for idx, (record, errors) in enumerate(invalid_records, 1):
            log_warning(f"  [{idx}] {record.package_name} (Record ID: {record.record_id})")
            for error in errors:
                log_warning(f"      - {error}")
            if record.children:
                log_info(f"      子记录数量: {len(record.children)}")
                for child_idx, child in enumerate(record.children, 1):
                    # 格式化提审时间
                    submission_time_str = "无"
                    if child.submission_time:
                        try:
                            dt = datetime.fromtimestamp(child.submission_time / 1000)
                            submission_time_str = dt.strftime('%Y-%m-%d')
                        except:
                            submission_time_str = str(child.submission_time)
                    
                    log_info(f"        子记录{child_idx}: 版本={child.version}, 状态={child.package_status}, 提审时间={submission_time_str}, ID={child.record_id}")
    
    log_endgroup()
    
    # 飞书通知配置（支持多个群，每个群可以配置不同的 @ 规则）
    # ⚠️ 请替换为实际的群聊 ID 和用户 ID
    FEISHU_NOTIFICATIONS = [
        {
            "chat_id": "oc_1de66c6e3d6dba470e302b2d474db39f",  # 群1 - 替换为实际的群聊 ID
            "mention_all": True  # @ 所有人
        },
        {
            "chat_id": "oc_26e985ac87884ce23bc1c181cf0f61dc",  # 群2 - 替换为实际的群聊 ID
            "mention_user_ids": [  # @ 多个用户（列表形式）
                "ou_15d061852fd73da48d30f629bf6301ae", # yuxiaoling
                "ou_3ce54c14f9ec3e6de326165614f4872d", # lanzhihong
                "ou_135b706486fe7cdd5c715d05ff23177e", # chenwenhan 
                "ou_162731495f6df9dfe218454ab39e0b26", # tangluoya 
                "ou_07f25dbb48dbb8d6c7adbec361eec97a", # suziwei
                  # 替换为实际的用户 open_id
                # "ou_yyyyyyyyyyyyyyyyyyyyyyyy",  # 可以添加更多用户
            ]
        }
    ]
    
    # 发送异常记录警告（调试期间暂时注释）
    if invalid_records:
        log_group("⚠️  步骤 6: 发送数据异常警告")
        # 找到配置了 mention_all = True 的群聊
        warning_chat_id = None
        for config in FEISHU_NOTIFICATIONS:
            if config.get("mention_all"):
                warning_chat_id = config.get("chat_id")
                break
        
        if warning_chat_id:
            monitor.send_warning_message(
                chat_id=warning_chat_id,
                invalid_records=invalid_records
            )
        else:
            log_warning("未找到配置 mention_all=True 的群聊，跳过发送警告")
        log_endgroup()
    
    # 查询每个 Apple ID 对应的版本，判断是否上线并更新状态（只处理有效记录）
    log_group("🍎 步骤 7: 查询 Apple Store 状态并更新")
    log_info(f"只处理有效记录（共 {len(valid_records)} 个）")
    
    # 获取当前时间戳（毫秒）
    current_timestamp = int(datetime.now().timestamp() * 1000)
    
    
    success_count = 0
    skip_count = 0
    
    for record in valid_records:
        if not record.apple_id:
            log_warning(f"{record.package_name} - 没有 Apple ID，跳过")
            skip_count += 1
            continue
        
        # 获取本地最新版本
        local_latest_version = record.get_latest_version()
        if not local_latest_version:
            log_warning(f"{record.package_name} - 没有最新版本，跳过")
            skip_count += 1
            continue
        
        # 查询 Apple Store 状态
        app_status = monitor.query_apple_app_status(record.apple_id, verbose=False)
        
        # 判断版本是否已上线
        is_version_online = False
        if app_status and app_status['is_online']:
            store_version = app_status['version']
            if store_version and store_version == local_latest_version:
                is_version_online = True
        
        # 处理已上线的应用
        if is_version_online:
            log_success(f"{record.package_name} - 指定版本已上线")
            log_info(f"  📱 应用名称: {app_status['track_name']}")
            log_info(f"  📦 版本号: {store_version} (本地最新版本: {local_latest_version})")
            log_info(f"  🆔 Apple ID: {record.apple_id}")
            log_info(f"  📅 发布日期: {app_status['release_date']}")
            log_info(f"  🔄 当前版本发布日期: {app_status['current_version_release_date']}")
            if app_status.get('track_view_url'):
                log_info(f"  🔗 应用链接: {app_status['track_view_url']}")
            
            # 更新飞书表格状态
            monitor.update_app_status(
                app_token=app_token,
                table_id=table_id,
                record=record,
                latest_version=local_latest_version,
                current_date_timestamp=current_timestamp
            )
            
            # 发送飞书通知到多个群聊（调试期间暂时注释）
            monitor.send_notifications(
                notifications=FEISHU_NOTIFICATIONS,
                app_name=record.package_name,
                stage=record.stage or "未知",
                version=local_latest_version
            )
            success_count += 1
        else:
            # 未上线的应用
            log_info(f"{record.package_name} - 指定版本未上线")
            log_info(f"  📱 应用名称: {record.package_name}")
            log_info(f"  📦 版本号: {local_latest_version}")
            log_info(f"  🆔 Apple ID: {record.apple_id}")
 
    log_endgroup()
    
    # 打印任务总结
    log_group("📊 任务执行总结")
    log_info(f"总共筛选: {len(filtered_records)} 个应用")
    log_info(f"有效记录: {len(valid_records)} 个")
    log_info(f"异常记录: {len(invalid_records)} 个")
    log_info(f"成功上线: {success_count} 个")
    log_info(f"跳过处理: {skip_count} 个")
    log_info(f"等待上线: {len(valid_records) - success_count - skip_count} 个")
    log_info(f"完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log_endgroup()
    
    return valid_records


if __name__ == "__main__":
    try:
        main()
        log_success("✅ 监控任务执行完成")
    except Exception as e:
        log_error(f"监控任务执行失败: {str(e)}")
        import traceback
        log_info(traceback.format_exc())
        exit(1)

