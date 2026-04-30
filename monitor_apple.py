"""
Apple 应用监控主程序
负责业务流程编排
"""
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Tuple

from config.settings import settings
from models.record import ApplePackageRecord
from services.apple_service import AppleStoreService
from services.feishu_messenger import FeishuMessenger
from services.feishu_service import FeishuBitableService
from utils.logger import (
    is_github_actions,
    log_endgroup,
    log_error,
    log_group,
    log_info,
    log_success,
    log_warning,
)
from utils.url_parser import parse_wiki_url


@dataclass
class MonitorCandidate:
    """当前需要做 Apple 上线监控的对象"""

    parent_record: ApplePackageRecord
    current_record: ApplePackageRecord
    apple_id: str
    version: str


class AppleMonitor:
    """Apple 应用监控类 - 负责业务流程编排"""

    def __init__(
        self,
        feishu_service: FeishuBitableService,
        feishu_messenger: FeishuMessenger,
        apple_service: AppleStoreService,
    ):
        self.feishu_service = feishu_service
        self.feishu_messenger = feishu_messenger
        self.apple_service = apple_service

    def evaluate_records(
        self,
        records: List[ApplePackageRecord],
        enable_record_review: bool = False,
    ) -> Tuple[List[MonitorCandidate], List[Tuple[ApplePackageRecord, List[str]]]]:
        """
        解析当前记录，并拆分出：
        1. 可选的项目管理记录审查问题
        2. Apple 上线监控候选
        """
        monitor_candidates: List[MonitorCandidate] = []
        review_issues: List[Tuple[ApplePackageRecord, List[str]]] = []

        for record in records:
            if not record.is_in_review_scope():
                continue

            current_record = record.resolve_current_submission_record()
            if record.children and not current_record:
                if enable_record_review:
                    parent_review = record.review_parent_snapshot()
                    if not parent_review["is_valid"]:
                        review_issues.append((record, parent_review["errors"]))

                    review_issues.append((record, ["父记录为提审中，但没有提审中的子记录"]))
                continue

            if not current_record:
                continue

            if enable_record_review and record.children:
                parent_review = record.review_parent_snapshot(current_record)
                if not parent_review["is_valid"]:
                    review_issues.append((record, parent_review["errors"]))

                submitting_children = record.get_submitting_children()
                if len(submitting_children) > 1:
                    review_issues.append(
                        (
                            record,
                            [
                                f"存在{len(submitting_children)}条提审中子记录，"
                                f"已按提审时间和版本号选择最新记录 ({current_record.record_id})"
                            ],
                        )
                    )

            if enable_record_review:
                current_review = current_record.review_current_submission()
                if not current_review["is_valid"]:
                    review_issues.append((current_record, current_review["errors"]))

            if not current_record.should_monitor_online():
                log_info(
                    f"{current_record.package_name or record.package_name} - "
                    f"当前记录阶段为 {current_record.stage}，跳过 Apple 上线监控"
                )
                continue

            apple_id = current_record.resolve_monitor_apple_id(record)
            online_errors = []
            if not apple_id:
                online_errors.append("缺少 Apple ID，无法监控上线")
            if not current_record.version:
                online_errors.append("缺少版本号，无法监控上线")

            if online_errors:
                if enable_record_review:
                    review_issues.append((current_record, online_errors))
                else:
                    log_warning(
                        f"{current_record.package_name or record.package_name} - "
                        f"跳过 Apple 上线监控: {'；'.join(online_errors)}"
                    )
                continue

            monitor_candidates.append(
                MonitorCandidate(
                    parent_record=record,
                    current_record=current_record,
                    apple_id=str(apple_id),
                    version=current_record.version,
                )
            )

        return monitor_candidates, review_issues

    def update_app_status(
        self,
        app_token: str,
        table_id: str,
        parent_record: ApplePackageRecord,
        current_record: ApplePackageRecord,
        current_date_timestamp: int,
    ) -> None:
        """
        更新应用的飞书表格状态

        - 单记录模式：更新当前记录的状态和过审时间
        - 父子模式：更新当前子记录的状态和过审时间，再更新父记录快照状态
        """
        log_info("📝 更新飞书表格状态...")

        if current_record.record_id != parent_record.record_id:
            log_info(f"  更新当前子记录: {current_record.record_id} (版本: {current_record.version})")
            child_updated = self.feishu_service.update_record_fields(
                app_token=app_token,
                table_id=table_id,
                record_id=current_record.record_id,
                fields={
                    "包状态": "已发布",
                    "过审时间": current_date_timestamp,
                },
            )
            if not child_updated:
                log_warning("  当前子记录更新失败，跳过父记录快照更新")
                return

            log_info(f"  更新父记录快照: {parent_record.record_id}")
            self.feishu_service.update_record_fields(
                app_token=app_token,
                table_id=table_id,
                record_id=parent_record.record_id,
                fields={"包状态": "已发布"},
            )
            return

        log_info(f"  更新单记录: {current_record.record_id}")
        self.feishu_service.update_record_fields(
            app_token=app_token,
            table_id=table_id,
            record_id=current_record.record_id,
            fields={
                "包状态": "已发布",
                "过审时间": current_date_timestamp,
            },
        )

    def auto_fix_parent_snapshot(
        self,
        app_token: str,
        table_id: str,
        parent_record: ApplePackageRecord,
        current_record: Optional[ApplePackageRecord],
    ) -> bool:
        """
        自动修正父记录快照：
        - 同步阶段
        - 同步包状态
        - 清空提审时间
        """
        fields = {}

        if current_record:
            if current_record.stage is not None and parent_record.stage != current_record.stage:
                fields["阶段"] = current_record.stage
            if (
                current_record.package_status is not None
                and parent_record.package_status != current_record.package_status
            ):
                fields["包状态"] = current_record.package_status

        if parent_record.submission_time is not None:
            fields["提审时间"] = None

        if not fields:
            return False

        log_info(f"🛠️ 自动修正父记录快照: {parent_record.record_id}")
        return self.feishu_service.update_record_fields(
            app_token=app_token,
            table_id=table_id,
            record_id=parent_record.record_id,
            fields=fields,
        )

    def run(self) -> List[MonitorCandidate]:
        """
        运行监控任务

        Returns:
            Apple 上线监控候选列表
        """
        log_group("🚀 Apple 应用监控任务开始")
        log_info(f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        log_info(f"运行环境: {'GitHub Actions' if is_github_actions() else 'Local'}")
        log_endgroup()

        if not settings.validate():
            log_error("缺少必要的环境变量")
            log_info("请设置以下环境变量：")
            log_info("  - FEISHU_APP_ID")
            log_info("  - FEISHU_APP_SECRET")
            log_info("  - FEISHU_WIKI_URL")
            return []

        log_group("📋 步骤 0: 解析 Wiki URL")
        wiki_node_token, table_id, view_id = parse_wiki_url(settings.FEISHU_WIKI_URL)
        if not wiki_node_token:
            log_error("无法从 URL 中提取 wiki 节点 token")
            log_endgroup()
            return []

        log_info(f"Wiki 节点 token: {wiki_node_token}")
        log_info(f"Table ID: {table_id}")
        log_info(f"View ID: {view_id}")
        log_endgroup()

        log_group("🔑 步骤 1: 从知识库节点获取 app_token")
        app_token = self.feishu_service.get_app_token_from_wiki(wiki_node_token)
        if not app_token:
            log_error("无法获取 app_token")
            log_info("   请检查：")
            log_info("   1. 应用是否有访问知识库的权限")
            log_info("   2. wiki_node_token 是否正确")
            log_info("   3. 节点是否是多维表格类型")
            log_endgroup()
            return []
        log_endgroup()

        log_group("🔌 步骤 2: 测试连接")
        if not self.feishu_service.test_connection(app_token):
            log_error("连接失败，请检查 app_token 是否正确")
            log_endgroup()
            return []
        log_endgroup()

        log_group("📊 步骤 3: 读取并构建记录分组")
        if not table_id:
            log_error("未找到 table_id，无法继续")
            log_endgroup()
            return []

        grouped_records = self.feishu_service.get_grouped_records(
            app_token=app_token,
            table_id=table_id,
            view_id=view_id,
        )
        log_endgroup()

        log_group("🧾 步骤 4: 解析当前记录")
        monitor_candidates, review_issues = self.evaluate_records(
            grouped_records,
            enable_record_review=settings.ENABLE_RECORD_REVIEW,
        )
        active_review_groups = [record for record in grouped_records if record.is_in_review_scope()]
        log_info(f"当前审核中记录组: {len(active_review_groups)}")
        if settings.ENABLE_RECORD_REVIEW:
            log_info(f"项目管理审查告警: {len(review_issues)} 条")
        else:
            log_info("项目管理审查: 已关闭 (ENABLE_RECORD_REVIEW=false)")
        log_info(f"Apple 监控候选: {len(monitor_candidates)} 条")

        if settings.ENABLE_RECORD_REVIEW and review_issues:
            log_info("审查问题详情：")
            for idx, (record, errors) in enumerate(review_issues, 1):
                log_warning(f"  [{idx}] {record.package_name} (Record ID: {record.record_id})")
                for error in errors:
                    log_warning(f"      - {error}")
        log_endgroup()

        if settings.ENABLE_RECORD_REVIEW and review_issues:
            log_group("⚠️  步骤 5: 发送项目管理审查告警")
            warning_chat_id = None
            for config in settings.FEISHU_NOTIFICATIONS:
                if config.get("mention_all"):
                    warning_chat_id = config.get("chat_id")
                    break

            if warning_chat_id:
                self.feishu_messenger.send_warning_message(
                    chat_id=warning_chat_id,
                    invalid_records=review_issues,
                )
            else:
                log_warning("未找到配置 mention_all=True 的群聊，跳过发送告警")
            log_endgroup()
        elif not settings.ENABLE_RECORD_REVIEW:
            log_group("⚠️  步骤 5: 跳过项目管理审查告警")
            log_info("ENABLE_RECORD_REVIEW=false，未收集或发送项目管理审查告警")
            log_endgroup()

        log_group("🛠️ 步骤 5.5: 自动修正父记录快照")
        parent_fix_count = 0
        for record in grouped_records:
            if not record.is_in_review_scope() or not record.children:
                continue

            current_record = record.resolve_current_submission_record()
            if self.auto_fix_parent_snapshot(
                app_token=app_token,
                table_id=table_id,
                parent_record=record,
                current_record=current_record,
            ):
                parent_fix_count += 1

        log_info(f"已自动修正父记录快照: {parent_fix_count} 条")
        log_endgroup()

        log_group("🍎 步骤 6: 查询 Apple Store 状态并更新")
        log_info(f"只处理 Apple 监控候选（共 {len(monitor_candidates)} 个）")

        current_timestamp = int(datetime.now().timestamp() * 1000)
        success_count = 0
        waiting_count = 0
        query_failed_count = 0
        lookup_result = self.apple_service.query_app_statuses_with_meta(
            [candidate.apple_id for candidate in monitor_candidates],
            verbose=False,
        )
        status_by_apple_id = lookup_result.status_by_apple_id
        failed_lookup_ids = set(lookup_result.failed_apple_ids)

        log_info(
            f"去重后 Apple ID: {len(status_by_apple_id)} 个，分 {lookup_result.total_batches} 批查询"
        )
        log_info(f"查询成功批次: {lookup_result.successful_batches}")
        if lookup_result.failed_batches:
            log_warning(f"查询失败批次: {lookup_result.failed_batches}")

        for candidate in monitor_candidates:
            if candidate.apple_id in failed_lookup_ids:
                log_warning(
                    f"{candidate.parent_record.package_name} - Apple 状态查询失败，跳过本轮判定"
                )
                log_warning(f"  🆔 Apple ID: {candidate.apple_id}")
                query_failed_count += 1
                continue

            app_status = status_by_apple_id.get(candidate.apple_id)

            is_version_online = False
            if app_status and app_status["is_online"]:
                store_version = app_status["version"]
                if store_version and store_version == candidate.version:
                    is_version_online = True

            if is_version_online:
                log_info(f"{candidate.parent_record.package_name} - 指定版本已上线")
                log_info(f"  📱 应用名称: {app_status['track_name']}")
                log_info(f"  📦 版本号: {store_version} (当前监控版本: {candidate.version})")
                log_info(f"  🆔 Apple ID: {candidate.apple_id}")
                log_info(f"  📅 发布日期: {app_status['release_date']}")
                log_info(f"  🔄 当前版本发布日期: {app_status['current_version_release_date']}")
                if app_status.get("track_view_url"):
                    log_info(f"  🔗 应用链接: {app_status['track_view_url']}")

                self.update_app_status(
                    app_token=app_token,
                    table_id=table_id,
                    parent_record=candidate.parent_record,
                    current_record=candidate.current_record,
                    current_date_timestamp=current_timestamp,
                )

                self.feishu_messenger.send_notifications(
                    notifications=settings.FEISHU_NOTIFICATIONS,
                    app_name=candidate.parent_record.package_name,
                    stage=candidate.current_record.stage or "未知",
                    version=candidate.version,
                )
                success_count += 1
            else:
                log_info(f"{candidate.parent_record.package_name} - 指定版本未上线")
                log_info(f"  📦 当前监控版本: {candidate.version}")
                log_info(f"  🆔 Apple ID: {candidate.apple_id}")
                waiting_count += 1

        log_endgroup()

        log_group("📊 任务执行总结")
        log_info(f"总共读取主记录组: {len(grouped_records)} 个")
        if settings.ENABLE_RECORD_REVIEW:
            log_info(f"项目管理审查告警: {len(review_issues)} 条")
        else:
            log_info("项目管理审查: 已关闭")
        log_info(f"Apple 监控候选: {len(monitor_candidates)} 个")
        log_info(f"Apple 查询批次: {lookup_result.total_batches}")
        log_info(f"Apple 查询成功批次: {lookup_result.successful_batches}")
        log_info(f"Apple 查询失败批次: {lookup_result.failed_batches}")
        log_info(f"成功上线: {success_count} 个")
        log_info(f"等待上线: {waiting_count} 个")
        log_info(f"查询失败: {query_failed_count} 个")
        log_info(f"完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        log_endgroup()

        return monitor_candidates


def main():
    """主函数"""
    feishu_service = FeishuBitableService(
        app_id=settings.FEISHU_APP_ID,
        app_secret=settings.FEISHU_APP_SECRET,
    )

    feishu_messenger = FeishuMessenger(
        app_id=settings.FEISHU_APP_ID,
        app_secret=settings.FEISHU_APP_SECRET,
        message_prefix=settings.FEISHU_MESSAGE_PREFIX,
    )

    apple_service = AppleStoreService()

    monitor = AppleMonitor(
        feishu_service=feishu_service,
        feishu_messenger=feishu_messenger,
        apple_service=apple_service,
    )

    monitor.run()


if __name__ == "__main__":
    try:
        main()
        log_success("✅ 监控任务执行完成")
    except Exception as e:
        log_error(f"监控任务执行失败: {str(e)}")
        import traceback

        log_info(traceback.format_exc())
        exit(1)
