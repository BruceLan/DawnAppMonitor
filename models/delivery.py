from dataclasses import dataclass
from typing import Optional, TypedDict

from models.record import ApplePackageRecord


class DeliveryAppStatus(TypedDict):
    """可投放同步阶段复用的 Apple lookup 结果"""

    is_online: bool
    version: Optional[str]
    track_name: Optional[str]
    release_date: Optional[str]
    current_version_release_date: Optional[str]
    bundle_id: Optional[str]
    track_view_url: Optional[str]


@dataclass
class ApprovedDeliveryItem:
    """Apple 已确认上线后，交给可投放同步的紧凑载体"""

    parent_record: ApplePackageRecord
    current_record: ApplePackageRecord
    apple_id: str
    app_status: DeliveryAppStatus
