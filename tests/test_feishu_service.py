import unittest
from unittest.mock import Mock, patch

from models.record import ApplePackageRecord
from services.feishu_service import FeishuBitableService


class FeishuBitableServiceTests(unittest.TestCase):
    def test_batch_create_records_uses_open_id_and_chunks_payload(self):
        service = FeishuBitableService(app_id="app-id", app_secret="app-secret")
        service.client = Mock()

        first_response = Mock()
        first_response.success.return_value = True
        first_response.data.records = [Mock(record_id="rec-1"), Mock(record_id="rec-2")]

        second_response = Mock()
        second_response.success.return_value = True
        second_response.data.records = [Mock(record_id="rec-3")]

        service.client.bitable.v1.app_table_record.batch_create.side_effect = [
            first_response,
            second_response,
        ]

        created_ids = service.batch_create_records(
            app_token="app-token",
            table_id="table-id",
            records=[
                {"AppleId": "1"},
                {"AppleId": "2"},
                {"AppleId": "3"},
            ],
            batch_size=2,
        )

        self.assertEqual(["rec-1", "rec-2", "rec-3"], created_ids)
        self.assertEqual(2, service.client.bitable.v1.app_table_record.batch_create.call_count)

        first_request = service.client.bitable.v1.app_table_record.batch_create.call_args_list[0].args[0]
        second_request = service.client.bitable.v1.app_table_record.batch_create.call_args_list[1].args[0]

        self.assertEqual("open_id", first_request.user_id_type)
        self.assertEqual("app-token", first_request.app_token)
        self.assertEqual("table-id", first_request.table_id)
        self.assertEqual(2, len(first_request.request_body.records))
        self.assertEqual(1, len(second_request.request_body.records))

    @patch("services.feishu_service.log_info")
    def test_get_grouped_records_logs_only_summary_not_each_parent_record(self, mock_log_info):
        service = FeishuBitableService(app_id="app-id", app_secret="app-secret")
        service.get_all_records = Mock(return_value=[{"record_id": "rec-1", "fields": {}}])
        service.build_record_groups = Mock(
            return_value=[
                ApplePackageRecord(record_id="rec-parent-1", package_name="Parent A"),
                ApplePackageRecord(record_id="rec-parent-2", package_name="Parent B"),
            ]
        )

        grouped_records = service.get_grouped_records(
            app_token="app-token",
            table_id="table-id",
            view_id="view-id",
        )

        self.assertEqual(2, len(grouped_records))
        self.assertTrue(
            any("构建完成，共找到 2 个主记录组" in str(call.args[0]) for call in mock_log_info.call_args_list)
        )
        self.assertFalse(
            any("主记录 " in str(call.args[0]) for call in mock_log_info.call_args_list)
        )


if __name__ == "__main__":
    unittest.main()
