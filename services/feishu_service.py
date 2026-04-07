"""
飞书多维表格服务模块
"""
from collections import defaultdict
from typing import Any, Dict, List, Optional

import lark_oapi as lark
from lark_oapi.api.bitable.v1 import (
    ListAppTableRecordRequest,
    ListAppTableRequest,
    UpdateAppTableRecordRequest
)
from lark_oapi.api.wiki.v2.model.get_node_space_request import GetNodeSpaceRequest
from models.record import ApplePackageRecord
from utils.logger import log_error, log_info, log_warning


class FeishuBitableService:
    """飞书多维表格服务类"""
    
    def __init__(self, app_id: str, app_secret: str):
        """
        初始化飞书客户端
        
        Args:
            app_id: 飞书应用的 App ID
            app_secret: 飞书应用的 App Secret
        """
        self.app_id = app_id
        self.app_secret = app_secret
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
                
                log_info(f"  - 节点类型: {obj_type}")
                log_info(f"  - obj_token (app_token): {obj_token}")
                
                if obj_type == "bitable":
                    log_info("确认是多维表格节点")
                    return obj_token
                else:
                    log_warning(f"节点类型不是多维表格 (bitable)，而是: {obj_type}")
                    return None
            else:
                log_error(f"获取节点信息失败: {response.code}, {response.msg}")
                log_info("\n可能的原因：")
                log_info("1. 应用没有访问知识库的权限")
                log_info("2. wiki_node_token 不正确")
                log_info("3. 节点不存在或已被删除")
                return None
        except Exception as e:
            log_error(f"获取节点信息异常: {str(e)}")
            return None
    
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
                log_info(f"连接成功！找到 {len(tables)} 个表格")
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

    @staticmethod
    def _extract_parent_ids(fields: Dict[str, Any], parent_field: str, record_id: str) -> List[str]:
        """从父记录字段中提取父记录 ID"""
        parent_ids = []
        parent_value = fields.get(parent_field)

        if not parent_value:
            return parent_ids

        if isinstance(parent_value, dict):
            parent_value = [parent_value]

        if not isinstance(parent_value, list):
            return parent_ids

        for item in parent_value:
            if not isinstance(item, dict):
                continue

            if item.get("id") and item.get("id") != record_id:
                parent_ids.append(item["id"])

            record_ids = item.get("record_ids") or []
            if isinstance(record_ids, list):
                parent_ids.extend(parent_id for parent_id in record_ids if parent_id and parent_id != record_id)

        # 保持顺序去重
        unique_parent_ids = []
        seen = set()
        for parent_id in parent_ids:
            if parent_id in seen:
                continue
            seen.add(parent_id)
            unique_parent_ids.append(parent_id)

        return unique_parent_ids

    @classmethod
    def build_record_groups(
        cls, raw_records: List[Dict[str, Any]], parent_field: str = "父记录"
    ) -> List[ApplePackageRecord]:
        """把平铺记录构造成父子分组"""
        records_by_id: Dict[str, ApplePackageRecord] = {}
        ordered_records: List[ApplePackageRecord] = []
        parent_ids_by_record: Dict[str, List[str]] = {}
        children_by_parent: Dict[str, List[ApplePackageRecord]] = defaultdict(list)

        for raw_record in raw_records:
            fields = raw_record.get("fields") or {}
            record_id = raw_record.get("record_id")
            if not record_id:
                continue

            package_record = ApplePackageRecord.from_feishu_fields(fields=fields, record_id=record_id)
            records_by_id[record_id] = package_record
            ordered_records.append(package_record)
            parent_ids_by_record[record_id] = cls._extract_parent_ids(fields, parent_field, record_id)

        for child_record in ordered_records:
            for parent_id in parent_ids_by_record.get(child_record.record_id, []):
                parent_record = records_by_id.get(parent_id)
                if not parent_record:
                    continue
                children_by_parent[parent_id].append(child_record)

        grouped_records = []
        for record in ordered_records:
            if parent_ids_by_record.get(record.record_id):
                continue
            record.children = children_by_parent.get(record.record_id, [])
            grouped_records.append(record)

        return grouped_records

    def get_grouped_records(
        self,
        app_token: str,
        table_id: str,
        view_id: Optional[str] = None,
        parent_field: str = "父记录"
    ) -> List[ApplePackageRecord]:
        """
        获取指定视图下的父子分组记录
        """
        log_info("开始读取多维表格并构建父子记录组...")
        log_info(f"  table_id: {table_id}")
        if view_id:
            log_info(f"  view_id: {view_id} (指定视图)")

        all_raw_records = self.get_all_records(app_token, table_id, view_id)
        log_info(f"  共获取 {len(all_raw_records)} 条记录")

        grouped_records = self.build_record_groups(all_raw_records, parent_field=parent_field)
        log_info(f"构建完成，共找到 {len(grouped_records)} 个主记录组")
        for grouped_record in grouped_records:
            log_info(
                f"  主记录 {grouped_record.package_name} (ID: {grouped_record.record_id}) "
                f"有 {len(grouped_record.children)} 条子记录"
            )
        return grouped_records

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
            fields: 要更新的字段字典，例如 {"包状态": "已发布", "过审时间": 1234567890000}
        
        Returns:
            更新是否成功
        """
        try:
            # 构建请求
            request = UpdateAppTableRecordRequest.builder() \
                .app_token(app_token) \
                .table_id(table_id) \
                .record_id(record_id) \
                .build()

            # 直接传原始 dict，保留 None -> null，避免 SDK 把清空字段吞掉。
            request.request_body = {"fields": fields}
            request.body = {"fields": fields}
            
            # 发起请求
            response = self.client.bitable.v1.app_table_record.update(request)
            
            if response.success():
                # 格式化更新信息
                update_info = ", ".join([f"{k}={v}" for k, v in fields.items()])
                log_info(f"更新成功: Record ID {record_id} ({update_info})")
                return True
            else:
                log_error(f"更新失败: Record ID {record_id}")
                log_info(f"  错误码: {response.code}")
                log_info(f"  错误信息: {response.msg}")
                return False
                
        except Exception as e:
            log_error(f"更新异常: Record ID {record_id}, 错误: {str(e)}")
            return False
