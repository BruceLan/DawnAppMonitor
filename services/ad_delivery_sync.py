"""
可投放表同步服务
"""
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse, urlunparse

from models.delivery import ApprovedDeliveryItem
from models.record import ApplePackageRecord
from services.feishu_service import FeishuBitableService
from utils.logger import log_info, log_warning
from utils.url_parser import parse_wiki_url


class AdDeliverySyncService:
    """把已确认上线的五图包同步到可投放表"""

    def __init__(
        self,
        feishu_service: FeishuBitableService,
    ):
        self.feishu_service = feishu_service

    @staticmethod
    def _is_delivery_stage(stage: Optional[str]) -> bool:
        return bool(stage and "五图" in stage)

    @staticmethod
    def _pick_first_user_id(*records: Optional[ApplePackageRecord]) -> Optional[str]:
        for record in records:
            if not record or not record.developers:
                continue
            for developer in record.developers:
                if developer and developer.id:
                    return developer.id
        return None

    @staticmethod
    def _normalize_field_text(value: object) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, list):
            if not value:
                return None
            return AdDeliverySyncService._normalize_field_text(value[0])
        if isinstance(value, dict):
            for key in ("text", "link", "name", "id"):
                field_value = value.get(key)
                if field_value:
                    return str(field_value)
            return None
        return str(value)

    @staticmethod
    def _build_url_cell(url: Optional[str]) -> Optional[dict]:
        if not url:
            return None
        return {"text": url, "link": url}

    @staticmethod
    def _normalize_store_url(url: Optional[str]) -> Optional[str]:
        if not url:
            return None
        parsed = urlparse(url.strip())
        if not parsed.scheme or not parsed.netloc:
            return url.strip()
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))

    @staticmethod
    def _extract_adjust_app_token(ad_aj_info: Optional[str]) -> Optional[str]:
        if not ad_aj_info:
            return None
        match = re.search(r"App token:\s*([^\s\n]+)", str(ad_aj_info))
        if match:
            return match.group(1).strip()
        return None

    def _filter_new_items(
        self,
        items: List[ApprovedDeliveryItem],
        existing_by_apple_id: Dict[str, Dict[str, Any]],
    ) -> List[ApprovedDeliveryItem]:
        filtered_items: List[ApprovedDeliveryItem] = []
        seen_apple_ids = set()

        for item in items:
            current_record = item.current_record
            parent_record = item.parent_record
            stage = current_record.stage or parent_record.stage
            if not self._is_delivery_stage(stage):
                continue

            if not item.app_status.get("is_online"):
                log_info(f"AppleId={item.apple_id} 当前未确认上线，跳过可投放表同步")
                continue

            if item.apple_id in existing_by_apple_id:
                log_info(f"AppleId={item.apple_id} 已存在于可投放表，跳过同步")
                continue

            if item.apple_id in seen_apple_ids:
                log_info(f"AppleId={item.apple_id} 在本轮同步中重复出现，跳过后续重复项")
                continue

            production_package_name = (
                current_record.production_package_name or parent_record.production_package_name
            )
            if not production_package_name:
                continue

            app_name = current_record.package_name or parent_record.package_name
            if not app_name:
                continue

            filtered_items.append(item)
            seen_apple_ids.add(item.apple_id)

        return filtered_items

    def _build_batch_fields(
        self,
        item: ApprovedDeliveryItem,
    ) -> Dict[str, object]:
        current_record = item.current_record
        parent_record = item.parent_record
        app_name = current_record.package_name or parent_record.package_name
        team = current_record.team or parent_record.team
        production_package_name = (
            current_record.production_package_name or parent_record.production_package_name
        )

        fields: Dict[str, object] = {
            "应用名": app_name,
            "团队": team,
            "AppleId": item.apple_id,
            "包名": production_package_name,
            "投放状态": "未投放",
        }

        developer_open_id = self._pick_first_user_id(current_record, parent_record)
        if developer_open_id:
            fields["研发"] = [{"id": developer_open_id}]

        adjust_app_token = self._extract_adjust_app_token(
            current_record.af_aj_info or parent_record.af_aj_info
        )
        if adjust_app_token:
            fields["Adjust信息"] = adjust_app_token

        store_link = self._build_url_cell(
            self._normalize_store_url(item.app_status.get("track_view_url"))
        )
        if store_link:
            fields["商店链接"] = store_link

        return fields

    def sync_delivery_records(self, items: List[ApprovedDeliveryItem], delivery_wiki_url: str) -> int:
        """把已确认上线的五图候选同步到可投放表"""
        if not items:
            log_info("没有已上线记录需要同步到可投放表")
            return 0

        wiki_node_token, table_id, _ = parse_wiki_url(delivery_wiki_url)
        if not wiki_node_token or not table_id:
            log_warning("AD_DELIVERY_WIKI_URL 解析失败，跳过可投放表同步")
            return 0

        app_token = self.feishu_service.get_app_token_from_wiki(wiki_node_token)
        if not app_token:
            log_warning("可投放表 app_token 获取失败，跳过同步")
            return 0

        destination_records = self.feishu_service.get_all_records(
            app_token=app_token,
            table_id=table_id,
        )
        existing_by_apple_id = {}
        for destination_record in destination_records:
            apple_id = self._normalize_field_text(destination_record.get("fields", {}).get("AppleId"))
            if apple_id:
                existing_by_apple_id[apple_id] = destination_record

        new_items = self._filter_new_items(items, existing_by_apple_id)
        if not new_items:
            log_info("没有新的可投放记录需要写入目标表")
            return 0

        batch_fields = [
            self._build_batch_fields(item)
            for item in new_items
        ]
        created_record_ids = self.feishu_service.batch_create_records(
            app_token=app_token,
            table_id=table_id,
            records=batch_fields,
            user_id_type="open_id",
        )
        return len(created_record_ids)
