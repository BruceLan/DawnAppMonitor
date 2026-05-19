import unittest
from unittest.mock import Mock

from models.delivery import ApprovedDeliveryItem
from models.record import ApplePackageRecord, UserInfo
from services.ad_delivery_sync import AdDeliverySyncService


class DeliverySyncTests(unittest.TestCase):
    def setUp(self):
        self.feishu_service = Mock()
        self.service = AdDeliverySyncService(
            feishu_service=self.feishu_service,
        )

    def _build_item(
        self,
        *,
        apple_id: str,
        team: str = "极光",
        stage: str = "A1+A2+H5+五图",
        package_name: str = "Demo App",
        production_package_name: str = "com.demo.app",
        developer_id: str = "ou_dev_1",
        af_aj_info: str = "App token: tlc8p8377cw0\n购买 token: sd6gjs",
        track_view_url: str = "https://apps.apple.com/us/app/demo-app/id123",
    ) -> ApprovedDeliveryItem:
        parent_record = ApplePackageRecord(
            record_id=f"parent-{apple_id}",
            package_name=f"{package_name} Parent",
            package_status="已发布",
            team=team,
            developers=[UserInfo(id=developer_id, name="Dev 1")],
            af_aj_info=af_aj_info,
        )
        current_record = ApplePackageRecord(
            record_id=f"child-{apple_id}",
            package_name=package_name,
            package_status="已发布",
            stage=stage,
            team=team,
            apple_id=apple_id,
            production_package_name=production_package_name,
            developers=[UserInfo(id=developer_id, name="Dev 1")],
            af_aj_info=af_aj_info,
            approval_time=1778601600000,
        )
        return ApprovedDeliveryItem(
            parent_record=parent_record,
            current_record=current_record,
            apple_id=apple_id,
            app_status={
                "is_online": True,
                "version": "1.0.0",
                "track_name": package_name,
                "release_date": None,
                "current_version_release_date": None,
                "bundle_id": production_package_name,
                "track_view_url": track_view_url,
            },
        )

    def test_sync_delivery_records_does_not_require_apple_service_lookup(self):
        item = self._build_item(apple_id="123")
        self.feishu_service.get_app_token_from_wiki.return_value = "delivery-app-token"
        self.feishu_service.get_all_records.return_value = []
        self.feishu_service.ensure_field.return_value = "fld_lookup_url"
        self.feishu_service.batch_create_records.return_value = ["rec-1"]

        created_count = self.service.sync_delivery_records(
            [item],
            "https://example.com/wiki/node?table=tbl1&view=vew1",
        )

        self.assertEqual(1, created_count)
        self.feishu_service.batch_create_records.assert_called_once()
        self.feishu_service.create_record.assert_not_called()

    def test_sync_delivery_records_batch_creates_multiple_new_rows_once(self):
        item_1 = self._build_item(apple_id="123", package_name="Demo App 1")
        item_2 = self._build_item(
            apple_id="456",
            team="破晓",
            package_name="Demo App 2",
            production_package_name="com.demo.app.2",
            track_view_url="https://apps.apple.com/us/app/demo-app-2/id456",
        )
        self.feishu_service.get_app_token_from_wiki.return_value = "delivery-app-token"
        self.feishu_service.get_all_records.return_value = []
        self.feishu_service.ensure_field.return_value = "fld_lookup_url"
        self.feishu_service.batch_create_records.return_value = ["rec-1", "rec-2"]

        created_count = self.service.sync_delivery_records(
            [item_1, item_2],
            "https://example.com/wiki/node?table=tbl1&view=vew1",
        )

        self.assertEqual(2, created_count)
        self.feishu_service.batch_create_records.assert_called_once()
        call_kwargs = self.feishu_service.batch_create_records.call_args.kwargs
        self.assertEqual("delivery-app-token", call_kwargs["app_token"])
        self.assertEqual("tbl1", call_kwargs["table_id"])
        self.assertEqual("open_id", call_kwargs["user_id_type"])
        self.assertEqual(2, len(call_kwargs["records"]))
        self.assertEqual("123", call_kwargs["records"][0]["AppleId"])
        self.assertEqual("456", call_kwargs["records"][1]["AppleId"])
        self.assertEqual("未投放", call_kwargs["records"][0]["投放状态"])
        self.assertEqual("未投放", call_kwargs["records"][1]["投放状态"])

    def test_sync_delivery_records_skips_existing_and_same_run_duplicate_apple_ids(self):
        new_item = self._build_item(apple_id="123", package_name="New App")
        duplicate_item_1 = self._build_item(apple_id="456", package_name="Dup App 1")
        duplicate_item_2 = self._build_item(apple_id="456", package_name="Dup App 2")
        existing_item = self._build_item(apple_id="789", package_name="Existing App")
        self.feishu_service.get_app_token_from_wiki.return_value = "delivery-app-token"
        self.feishu_service.get_all_records.return_value = [
            {
                "record_id": "existing-rec",
                "fields": {
                    "AppleId": [{"text": "789", "link": "https://example.com"}],
                },
            }
        ]
        self.feishu_service.ensure_field.return_value = "fld_lookup_url"
        self.feishu_service.batch_create_records.return_value = ["rec-1", "rec-2"]

        created_count = self.service.sync_delivery_records(
            [new_item, duplicate_item_1, duplicate_item_2, existing_item],
            "https://example.com/wiki/node?table=tbl1&view=vew1",
        )

        self.assertEqual(2, created_count)
        self.feishu_service.update_record_fields.assert_not_called()
        self.feishu_service.create_record.assert_not_called()
        self.feishu_service.batch_create_records.assert_called_once()
        records = self.feishu_service.batch_create_records.call_args.kwargs["records"]
        self.assertEqual(["123", "456"], [record["AppleId"] for record in records])

    def test_sync_delivery_records_reads_target_table_once_and_normalizes_apple_id(self):
        normalized_existing_item = self._build_item(apple_id="123")
        self.feishu_service.get_app_token_from_wiki.return_value = "delivery-app-token"
        self.feishu_service.get_all_records.return_value = [
            {
                "record_id": "existing-rec",
                "fields": {
                    "AppleId": {"text": "123"},
                },
            }
        ]
        self.feishu_service.ensure_field.return_value = "fld_lookup_url"

        created_count = self.service.sync_delivery_records(
            [normalized_existing_item],
            "https://example.com/wiki/node?table=tbl1&view=vew1",
        )

        self.assertEqual(0, created_count)
        self.feishu_service.get_all_records.assert_called_once_with(
            app_token="delivery-app-token",
            table_id="tbl1",
        )
        self.feishu_service.batch_create_records.assert_not_called()

    def test_sync_delivery_records_keeps_source_team_without_whitelist_filter(self):
        item = self._build_item(apple_id="234", team="静界")
        self.feishu_service.get_app_token_from_wiki.return_value = "delivery-app-token"
        self.feishu_service.get_all_records.return_value = []
        self.feishu_service.ensure_field.return_value = "fld_lookup_url"
        self.feishu_service.batch_create_records.return_value = ["rec-1"]

        created_count = self.service.sync_delivery_records(
            [item],
            "https://example.com/wiki/node?table=tbl1&view=vew1",
        )

        self.assertEqual(1, created_count)
        self.feishu_service.batch_create_records.assert_called_once()
        records = self.feishu_service.batch_create_records.call_args.kwargs["records"]
        self.assertEqual("静界", records[0]["团队"])


if __name__ == "__main__":
    unittest.main()
