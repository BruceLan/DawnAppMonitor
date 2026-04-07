"""
飞书多维表格数据模型
用于映射和存储从飞书多维表格读取的记录数据
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from packaging import version


@dataclass
class FileInfo:
    """文件信息模型"""

    file_token: Optional[str] = None
    name: Optional[str] = None
    size: Optional[int] = None
    tmp_url: Optional[str] = None
    type: Optional[str] = None
    url: Optional[str] = None


@dataclass
class LinkInfo:
    """链接信息模型"""

    link: str
    text: str


@dataclass
class UserInfo:
    """用户信息模型"""

    id: str
    name: str
    email: Optional[str] = None
    en_name: Optional[str] = None
    avatar_url: Optional[str] = None


@dataclass
class ParentRecord:
    """父记录引用模型"""

    id: Optional[str] = None
    table_id: Optional[str] = None
    record_ids: Optional[List[str]] = None
    text: Optional[str] = None
    text_arr: Optional[List[str]] = None
    type: str = "text"


@dataclass
class ApplePackageRecord:
    """Apple 包记录模型"""

    apple_id: Optional[str] = None
    package_name: Optional[str] = None
    package_status: Optional[str] = None
    version: Optional[str] = None
    test_package_name: Optional[str] = None
    production_package_name: Optional[str] = None
    package_size: Optional[str] = None

    logo: Optional[List[FileInfo]] = None
    repository_url: Optional[LinkInfo] = None

    product_code: Optional[str] = None
    team: Optional[str] = None
    quarter: Optional[str] = None
    stage: Optional[str] = None
    h5_versions: Optional[List[str]] = None

    developers: Optional[List[UserInfo]] = None
    designers: Optional[List[UserInfo]] = None
    package_sender: Optional[List[UserInfo]] = None

    submission_time: Optional[int] = None
    approval_time: Optional[int] = None
    status_update_time: Optional[int] = None
    exception_time: Optional[int] = None

    af_aj_info: Optional[str] = None
    machine_location: Optional[str] = None
    development_days: Optional[float] = None
    application_topic: Optional[str] = None
    exception_category: Optional[str] = None
    refund_callback_url: Optional[str] = None
    privacy_policy: Optional[str] = None
    update_description: Optional[str] = None
    notes: Optional[str] = None
    white_package_usage: Optional[str] = None

    parent_record: Optional[List[ParentRecord]] = None
    record_id: Optional[str] = None
    children: List["ApplePackageRecord"] = field(default_factory=list)

    @staticmethod
    def _normalize_single_value(value: Any) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, list):
            if not value:
                return None
            return ApplePackageRecord._normalize_single_value(value[0])
        if isinstance(value, dict):
            for key in ("name", "text", "link", "url", "id"):
                if value.get(key):
                    return str(value[key])
            return None
        return str(value)

    @staticmethod
    def _normalize_multi_values(value: Any) -> Optional[List[str]]:
        if value is None:
            return None
        if not isinstance(value, list):
            normalized = ApplePackageRecord._normalize_single_value(value)
            return [normalized] if normalized else None

        normalized = []
        for item in value:
            item_value = ApplePackageRecord._normalize_single_value(item)
            if item_value:
                normalized.append(item_value)
        return normalized or None

    @staticmethod
    def _safe_version(value: Optional[str]):
        try:
            return version.parse(value or "0")
        except Exception:
            return version.parse("0")

    @staticmethod
    def _parse_timestamp(value: Any) -> Optional[int]:
        if value in (None, ""):
            return None

        if isinstance(value, (int, float)):
            return int(value)

        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return None

            try:
                return int(float(stripped))
            except (ValueError, TypeError):
                pass

            date_formats = (
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d",
                "%Y/%m/%d %H:%M:%S",
                "%Y/%m/%d",
            )
            for date_format in date_formats:
                try:
                    return int(datetime.strptime(stripped, date_format).timestamp() * 1000)
                except ValueError:
                    continue

            try:
                return int(datetime.fromisoformat(stripped).timestamp() * 1000)
            except ValueError:
                return None

        return None

    @classmethod
    def from_feishu_fields(
        cls, fields: Dict[str, Any], record_id: Optional[str] = None
    ) -> "ApplePackageRecord":
        """从飞书字段字典创建模型实例"""

        logo = None
        if fields.get("logo"):
            logo = [
                FileInfo(
                    file_token=item.get("file_token"),
                    name=item.get("name"),
                    size=item.get("size"),
                    tmp_url=item.get("tmp_url"),
                    type=item.get("type"),
                    url=item.get("url"),
                )
                for item in fields["logo"]
                if isinstance(item, dict)
            ] or None

        repository_url = None
        if fields.get("仓库地址"):
            repo_data = fields["仓库地址"]
            if isinstance(repo_data, dict):
                link = repo_data.get("link") or repo_data.get("url") or str(repo_data)
                text = repo_data.get("text") or link
                repository_url = LinkInfo(link=link, text=text)
            else:
                repository_url = LinkInfo(link=str(repo_data), text=str(repo_data))

        def parse_user_list(field_name: str) -> Optional[List[UserInfo]]:
            users = fields.get(field_name)
            if not users or not isinstance(users, list):
                return None

            parsed_users = []
            for user in users:
                if not isinstance(user, dict):
                    continue
                user_id = str(user.get("id") or "")
                user_name = str(user.get("name") or user.get("en_name") or user.get("email") or user_id)
                if not user_id and not user_name:
                    continue
                parsed_users.append(
                    UserInfo(
                        id=user_id or user_name,
                        name=user_name,
                        email=user.get("email"),
                        en_name=user.get("en_name"),
                        avatar_url=user.get("avatar_url"),
                    )
                )
            return parsed_users or None

        parent_record = None
        parent_data = fields.get("父记录")
        if parent_data and isinstance(parent_data, list):
            parsed_parents = []
            for item in parent_data:
                if not isinstance(item, dict):
                    continue
                parsed_parents.append(
                    ParentRecord(
                        id=item.get("id"),
                        table_id=item.get("table_id"),
                        record_ids=item.get("record_ids"),
                        text=item.get("text"),
                        text_arr=item.get("text_arr"),
                        type=item.get("type", "text"),
                    )
                )
            parent_record = parsed_parents or None

        return cls(
            record_id=record_id,
            apple_id=cls._normalize_single_value(fields.get("Apple ID")),
            package_name=cls._normalize_single_value(fields.get("包名")),
            package_status=cls._normalize_single_value(fields.get("包状态")),
            version=cls._normalize_single_value(fields.get("版本号")),
            test_package_name=cls._normalize_single_value(fields.get("测试包名")),
            production_package_name=cls._normalize_single_value(fields.get("生产包名")),
            package_size=cls._normalize_single_value(fields.get("包Size")),
            logo=logo,
            repository_url=repository_url,
            product_code=cls._normalize_single_value(fields.get("商品code")),
            team=cls._normalize_single_value(fields.get("团队")),
            quarter=cls._normalize_single_value(fields.get("所属季度")),
            stage=cls._normalize_single_value(fields.get("阶段")),
            h5_versions=cls._normalize_multi_values(fields.get("H5版本")),
            developers=parse_user_list("开发人员"),
            designers=parse_user_list("设计人员"),
            package_sender=parse_user_list("发包人员"),
            submission_time=cls._parse_timestamp(fields.get("提审时间")),
            approval_time=cls._parse_timestamp(fields.get("过审时间")),
            status_update_time=cls._parse_timestamp(fields.get("包状态更新时间")),
            exception_time=cls._parse_timestamp(fields.get("异常时间")),
            af_aj_info=cls._normalize_single_value(fields.get("是否申请AF/AJ")),
            machine_location=cls._normalize_single_value(fields.get("机器位置")),
            development_days=fields.get("开发人日"),
            application_topic=cls._normalize_single_value(fields.get("应用选题")),
            exception_category=cls._normalize_single_value(fields.get("异常类别")),
            refund_callback_url=cls._normalize_single_value(fields.get("退款回调地址")),
            privacy_policy=cls._normalize_single_value(fields.get("隐私协议")),
            update_description=cls._normalize_single_value(fields.get("更新文案")),
            notes=cls._normalize_single_value(fields.get("备注")),
            white_package_usage=cls._normalize_single_value(fields.get("白包使用情况")),
            parent_record=parent_record,
        )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        result = {}
        for key, value in self.__dict__.items():
            if value is None:
                continue
            if isinstance(value, list):
                result[key] = [item.__dict__ if hasattr(item, "__dict__") else item for item in value]
            elif hasattr(value, "__dict__"):
                result[key] = value.__dict__
            else:
                result[key] = value
        return result

    def get_submission_datetime(self) -> Optional[datetime]:
        """获取提审时间的 datetime 对象"""
        if self.submission_time:
            return datetime.fromtimestamp(self.submission_time / 1000)
        return None

    def get_approval_datetime(self) -> Optional[datetime]:
        """获取过审时间的 datetime 对象"""
        if self.approval_time:
            return datetime.fromtimestamp(self.approval_time / 1000)
        return None

    def get_submitting_children(self) -> List["ApplePackageRecord"]:
        """返回提审中的子记录"""
        return [child for child in self.children if child.package_status == "提审中"]

    def has_multiple_submitting_children(self) -> bool:
        """是否存在多条提审中的子记录"""
        return len(self.get_submitting_children()) > 1

    def is_in_review_scope(self) -> bool:
        """是否属于本次审核中的记录范围"""
        return self.package_status == "提审中"

    def resolve_current_submission_record(self) -> Optional["ApplePackageRecord"]:
        """
        返回当前要关注的发包流水

        - 单记录模式：记录本身处于提审中时返回自身
        - 父子模式：从提审中的子记录中，按提审时间倒序、版本号倒序选择最新一条
        """
        if not self.children:
            return self if self.package_status == "提审中" else None

        candidates = self.get_submitting_children()
        if not candidates:
            return None

        return sorted(
            candidates,
            key=lambda record: (
                record.submission_time or 0,
                self._safe_version(record.version),
                record.record_id or "",
            ),
            reverse=True,
        )[0]

    def resolve_monitor_apple_id(self, parent_record: Optional["ApplePackageRecord"] = None) -> Optional[str]:
        """返回用于 Apple 监控的 Apple ID，优先取当前记录，缺失时回退主记录"""
        return self.apple_id or (parent_record.apple_id if parent_record else None)

    def should_monitor_online(self) -> bool:
        """是否需要做 Apple 上线监控"""
        return self.stage != "五图"

    def review_parent_snapshot(
        self, current_record: Optional["ApplePackageRecord"] = None
    ) -> Dict[str, Any]:
        """审查父记录快照"""
        errors = []

        if self.submission_time:
            errors.append("父记录不应填写提审时间")
        if not self.package_status:
            errors.append("父记录缺少包状态")
        if not self.stage:
            errors.append("父记录缺少阶段")
        if current_record and self.package_status and self.package_status != current_record.package_status:
            errors.append("父记录包状态未同步最新状态")
        if current_record and self.stage and self.stage != current_record.stage:
            errors.append("父记录阶段未同步最新阶段")

        return {"is_valid": len(errors) == 0, "errors": errors}

    def review_current_submission(self) -> Dict[str, Any]:
        """审查当前发包流水"""
        errors = []

        if not self.submission_time:
            errors.append("缺少提审时间")
        if self.should_monitor_online() and not self.version:
            errors.append("缺少版本号")

        return {"is_valid": len(errors) == 0, "errors": errors}

    def get_latest_version(self) -> Optional[str]:
        """
        兼容旧接口：优先返回当前发包流水的版本号
        """
        if not self.is_in_review_scope():
            return None

        current_record = self.resolve_current_submission_record()
        if current_record and current_record.version:
            return current_record.version
        return self.version

    def validate_data(self) -> Dict[str, Any]:
        """
        兼容旧接口：审查当前发包流水
        """
        if not self.is_in_review_scope():
            return {"is_valid": True, "errors": []}

        current_record = self.resolve_current_submission_record()
        if self.children and not current_record:
            errors = []
            parent_review = self.review_parent_snapshot()
            if not parent_review["is_valid"]:
                errors.extend(parent_review["errors"])
            errors.append("父记录为提审中，但没有提审中的子记录")
            return {"is_valid": False, "errors": errors}

        if not current_record:
            return {"is_valid": True, "errors": []}
        return current_record.review_current_submission()
