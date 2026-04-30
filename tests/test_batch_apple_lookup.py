import unittest
from requests.exceptions import Timeout
from unittest.mock import Mock, patch

import monitor_apple
from models.record import ApplePackageRecord
from monitor_apple import AppleMonitor
from services.apple_service import AppleLookupResult, AppleStoreService


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class AppleStoreServiceBatchLookupTests(unittest.TestCase):
    @patch("services.apple_service.requests.get")
    def test_query_app_statuses_deduplicates_ids_and_marks_missing_results_offline(self, mock_get):
        mock_get.return_value = FakeResponse(
            {
                "resultCount": 1,
                "results": [
                    {
                        "trackId": 123,
                        "version": "1.2.3",
                        "trackName": "Demo App",
                        "releaseDate": "2026-04-29T00:00:00Z",
                        "currentVersionReleaseDate": "2026-04-29T00:00:00Z",
                        "bundleId": "com.demo.app",
                        "trackViewUrl": "https://apps.apple.com/app/id123",
                    }
                ],
            }
        )

        service = AppleStoreService()

        statuses = service.query_app_statuses(["123", "456", "123"])

        mock_get.assert_called_once_with(
            service.api_url,
            params={"id": "123,456", "country": "us"},
            timeout=10,
        )
        self.assertTrue(statuses["123"]["is_online"])
        self.assertEqual("1.2.3", statuses["123"]["version"])
        self.assertFalse(statuses["456"]["is_online"])
        self.assertIsNone(statuses["456"]["version"])

    @patch("services.apple_service.requests.get")
    def test_query_app_statuses_splits_requests_in_chunks_of_50(self, mock_get):
        mock_get.side_effect = [
            FakeResponse({"resultCount": 0, "results": []}),
            FakeResponse({"resultCount": 0, "results": []}),
        ]
        service = AppleStoreService()
        apple_ids = [str(index) for index in range(1, 52)]

        statuses = service.query_app_statuses(apple_ids)

        self.assertEqual(51, len(statuses))
        self.assertEqual(2, mock_get.call_count)
        first_call = mock_get.call_args_list[0]
        second_call = mock_get.call_args_list[1]
        self.assertEqual(
            {
                "id": ",".join(str(index) for index in range(1, 51)),
                "country": "us",
            },
            first_call.kwargs["params"],
        )
        self.assertEqual(
            {
                "id": "51",
                "country": "us",
            },
            second_call.kwargs["params"],
        )

    @patch("services.apple_service.time.sleep")
    @patch("services.apple_service.requests.get")
    def test_query_app_statuses_with_meta_retries_failed_batch_and_keeps_successful_batches(
        self, mock_get, _mock_sleep
    ):
        mock_get.side_effect = [
            FakeResponse(
                {
                    "resultCount": 1,
                    "results": [
                        {
                            "trackId": 1,
                            "version": "1.0.0",
                            "trackName": "Demo App",
                            "releaseDate": "2026-04-29T00:00:00Z",
                            "currentVersionReleaseDate": "2026-04-29T00:00:00Z",
                            "bundleId": "com.demo.app",
                            "trackViewUrl": "https://apps.apple.com/app/id1",
                        }
                    ],
                }
            ),
            Timeout("timeout-1"),
            Timeout("timeout-2"),
            Timeout("timeout-3"),
        ]
        service = AppleStoreService()
        apple_ids = [str(index) for index in range(1, 52)]

        lookup_result = service.query_app_statuses_with_meta(apple_ids)

        self.assertEqual(2, lookup_result.total_batches)
        self.assertEqual(1, lookup_result.successful_batches)
        self.assertEqual(1, lookup_result.failed_batches)
        self.assertEqual(["51"], lookup_result.failed_apple_ids)
        self.assertTrue(lookup_result.status_by_apple_id["1"]["is_online"])
        self.assertFalse(lookup_result.status_by_apple_id["51"]["is_online"])
        self.assertEqual(4, mock_get.call_count)
        self.assertEqual(2, _mock_sleep.call_count)


class AppleMonitorBatchLookupTests(unittest.TestCase):
    @patch("monitor_apple.parse_wiki_url", return_value=("wiki-token", "table-id", "view-id"))
    def test_run_uses_bulk_lookup_and_updates_only_matching_duplicate_apple_id(self, _mock_parse):
        record_online = ApplePackageRecord(
            record_id="record-online",
            package_name="Demo App A",
            package_status="提审中",
            version="1.2.3",
            stage="开发",
            apple_id="123",
        )
        record_waiting = ApplePackageRecord(
            record_id="record-waiting",
            package_name="Demo App B",
            package_status="提审中",
            version="9.9.9",
            stage="开发",
            apple_id="123",
        )

        feishu_service = Mock()
        feishu_service.get_app_token_from_wiki.return_value = "app-token"
        feishu_service.test_connection.return_value = True
        feishu_service.get_grouped_records.return_value = [record_online, record_waiting]
        feishu_service.update_record_fields.return_value = True

        feishu_messenger = Mock()

        apple_service = Mock()
        apple_service.query_app_statuses_with_meta.return_value = AppleLookupResult(
            status_by_apple_id={
                "123": {
                    "is_online": True,
                    "version": "1.2.3",
                    "track_name": "Demo App A",
                    "release_date": "2026-04-29T00:00:00Z",
                    "current_version_release_date": "2026-04-29T00:00:00Z",
                    "bundle_id": "com.demo.app",
                    "track_view_url": "https://apps.apple.com/app/id123",
                }
            },
            failed_apple_ids=[],
            total_batches=1,
            successful_batches=1,
            failed_batches=0,
        )

        monitor = AppleMonitor(
            feishu_service=feishu_service,
            feishu_messenger=feishu_messenger,
            apple_service=apple_service,
        )

        with patch.object(monitor_apple.settings, "validate", return_value=True), patch.object(
            monitor_apple.settings, "FEISHU_WIKI_URL", "https://example.com/wiki"
        ), patch.object(monitor_apple.settings, "FEISHU_NOTIFICATIONS", []), patch.object(
            monitor_apple.settings, "ENABLE_RECORD_REVIEW", False
        ):
            monitor.run()

        apple_service.query_app_statuses_with_meta.assert_called_once_with(["123", "123"], verbose=False)
        feishu_service.update_record_fields.assert_called_once()
        update_kwargs = feishu_service.update_record_fields.call_args.kwargs
        self.assertEqual("record-online", update_kwargs["record_id"])
        feishu_messenger.send_notifications.assert_called_once()

    @patch("monitor_apple.log_warning")
    @patch("monitor_apple.parse_wiki_url", return_value=("wiki-token", "table-id", "view-id"))
    def test_run_marks_failed_lookup_as_query_failed_not_waiting(self, _mock_parse, mock_log_warning):
        record_failed = ApplePackageRecord(
            record_id="record-failed",
            package_name="Demo App Failed",
            package_status="提审中",
            version="1.0.0",
            stage="开发",
            apple_id="123",
        )

        feishu_service = Mock()
        feishu_service.get_app_token_from_wiki.return_value = "app-token"
        feishu_service.test_connection.return_value = True
        feishu_service.get_grouped_records.return_value = [record_failed]
        feishu_service.update_record_fields.return_value = True

        feishu_messenger = Mock()
        apple_service = Mock()
        apple_service.query_app_statuses_with_meta.return_value = AppleLookupResult(
            status_by_apple_id={"123": AppleStoreService._build_offline_status()},
            failed_apple_ids=["123"],
            total_batches=1,
            successful_batches=0,
            failed_batches=1,
        )

        monitor = AppleMonitor(
            feishu_service=feishu_service,
            feishu_messenger=feishu_messenger,
            apple_service=apple_service,
        )

        with patch.object(monitor_apple.settings, "validate", return_value=True), patch.object(
            monitor_apple.settings, "FEISHU_WIKI_URL", "https://example.com/wiki"
        ), patch.object(monitor_apple.settings, "FEISHU_NOTIFICATIONS", []), patch.object(
            monitor_apple.settings, "ENABLE_RECORD_REVIEW", False
        ), patch("monitor_apple.log_info") as mock_log_info:
            monitor.run()

        apple_service.query_app_statuses_with_meta.assert_called_once_with(["123"], verbose=False)
        feishu_service.update_record_fields.assert_not_called()
        feishu_messenger.send_notifications.assert_not_called()
        self.assertTrue(
            any("Apple 状态查询失败，跳过本轮判定" in str(call.args[0]) for call in mock_log_warning.call_args_list)
        )
        self.assertFalse(
            any("指定版本未上线" in str(call.args[0]) for call in mock_log_info.call_args_list)
        )


if __name__ == "__main__":
    unittest.main()
