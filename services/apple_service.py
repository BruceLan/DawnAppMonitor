"""
Apple Store API 服务模块
"""
import json
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests

from utils.logger import log_error, log_info, log_warning


@dataclass
class AppleLookupResult:
    """Apple Lookup 批量查询结果"""

    status_by_apple_id: Dict[str, Dict[str, Any]]
    failed_apple_ids: List[str]
    total_batches: int
    successful_batches: int
    failed_batches: int


class AppleStoreService:
    """Apple Store API 服务类"""

    LOOKUP_BATCH_SIZE = 50
    LOOKUP_MAX_RETRIES = 2
    LOOKUP_RETRY_DELAYS = (1, 3)

    def __init__(self):
        self.api_url = "https://itunes.apple.com/lookup"

    @staticmethod
    def _build_offline_status() -> Dict[str, Any]:
        return {
            "is_online": False,
            "version": None,
            "track_name": None,
            "release_date": None,
            "current_version_release_date": None,
        }

    @staticmethod
    def _build_app_info(result: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "is_online": True,
            "version": result.get("version"),
            "track_name": result.get("trackName"),
            "release_date": result.get("releaseDate"),
            "current_version_release_date": result.get("currentVersionReleaseDate"),
            "bundle_id": result.get("bundleId"),
            "track_view_url": result.get("trackViewUrl"),
        }

    @staticmethod
    def _chunk_items(items: List[str], chunk_size: int) -> List[List[str]]:
        return [items[index:index + chunk_size] for index in range(0, len(items), chunk_size)]

    @staticmethod
    def _should_retry_request_error(error: requests.exceptions.RequestException) -> bool:
        response = getattr(error, "response", None)
        if response is not None and 400 <= response.status_code < 500:
            return False
        return True

    def _request_lookup_batch(
        self,
        batch_apple_ids: List[str],
        batch_index: int,
        total_batches: int,
        verbose: bool = False,
    ) -> Dict[str, Any]:
        params = {
            "id": ",".join(batch_apple_ids),
            "country": "us",
        }

        for attempt in range(self.LOOKUP_MAX_RETRIES + 1):
            try:
                log_info(
                    f"[Apple Lookup] 第 {batch_index}/{total_batches} 批，本批 {len(batch_apple_ids)} 个 ID"
                )
                if verbose:
                    log_info(f"  API URL: {self.api_url}")
                    log_info(f"  参数: {params}")

                response = requests.get(self.api_url, params=params, timeout=10)
                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as error:
                if attempt >= self.LOOKUP_MAX_RETRIES or not self._should_retry_request_error(error):
                    raise

                delay = self.LOOKUP_RETRY_DELAYS[min(attempt, len(self.LOOKUP_RETRY_DELAYS) - 1)]
                log_warning(
                    f"[Apple Lookup] 第 {batch_index}/{total_batches} 批请求失败，第 {attempt + 1} 次重试"
                )
                log_warning(f"  错误: {str(error)}")
                log_info(f"  {delay} 秒后重试")
                time.sleep(delay)

        raise RuntimeError("unreachable")

    def query_app_statuses_with_meta(
        self, apple_ids: List[str], verbose: bool = False
    ) -> AppleLookupResult:
        """
        批量查询多个 Apple 应用状态，返回状态映射及批次执行信息
        """
        unique_apple_ids = list(dict.fromkeys(str(apple_id) for apple_id in apple_ids if str(apple_id).strip()))
        if not unique_apple_ids:
            return AppleLookupResult(
                status_by_apple_id={},
                failed_apple_ids=[],
                total_batches=0,
                successful_batches=0,
                failed_batches=0,
            )

        batches = self._chunk_items(unique_apple_ids, self.LOOKUP_BATCH_SIZE)
        status_by_apple_id = {
            apple_id: self._build_offline_status()
            for apple_id in unique_apple_ids
        }
        failed_apple_ids: List[str] = []
        successful_batches = 0
        failed_batches = 0

        for batch_index, batch_apple_ids in enumerate(batches, start=1):
            try:
                data = self._request_lookup_batch(
                    batch_apple_ids=batch_apple_ids,
                    batch_index=batch_index,
                    total_batches=len(batches),
                    verbose=verbose,
                )
                for result in data.get("results", []):
                    track_id = result.get("trackId")
                    if track_id is None:
                        continue
                    status_by_apple_id[str(track_id)] = self._build_app_info(result)
                successful_batches += 1
            except requests.exceptions.RequestException as error:
                failed_batches += 1
                failed_apple_ids.extend(batch_apple_ids)
                log_error(f"[Apple Lookup] 第 {batch_index}/{len(batches)} 批最终失败")
                log_info(f"  错误: {str(error)}")
                log_info(f"  失败 ID 数: {len(batch_apple_ids)}")
                log_info(f"  失败 ID: {', '.join(batch_apple_ids)}")
            except json.JSONDecodeError as error:
                failed_batches += 1
                failed_apple_ids.extend(batch_apple_ids)
                log_error(f"[Apple Lookup] 第 {batch_index}/{len(batches)} 批 JSON 解析失败")
                log_info(f"  错误: {str(error)}")
                log_info(f"  失败 ID 数: {len(batch_apple_ids)}")
                log_info(f"  失败 ID: {', '.join(batch_apple_ids)}")
            except Exception as error:
                failed_batches += 1
                failed_apple_ids.extend(batch_apple_ids)
                log_error(f"[Apple Lookup] 第 {batch_index}/{len(batches)} 批查询异常")
                log_info(f"  错误: {str(error)}")
                log_info(f"  失败 ID 数: {len(batch_apple_ids)}")
                log_info(f"  失败 ID: {', '.join(batch_apple_ids)}")

        if verbose:
            failed_id_set = set(failed_apple_ids)
            missing_ids = [
                apple_id
                for apple_id, status in status_by_apple_id.items()
                if not status["is_online"] and apple_id not in failed_id_set
            ]
            for apple_id in missing_ids:
                log_warning(f"未找到应用信息（Apple ID: {apple_id}）")

        return AppleLookupResult(
            status_by_apple_id=status_by_apple_id,
            failed_apple_ids=failed_apple_ids,
            total_batches=len(batches),
            successful_batches=successful_batches,
            failed_batches=failed_batches,
        )

    def query_app_statuses(
        self, apple_ids: List[str], verbose: bool = False
    ) -> Dict[str, Dict[str, Any]]:
        """兼容旧接口：只返回按 Apple ID 建立的状态映射"""
        return self.query_app_statuses_with_meta(apple_ids, verbose=verbose).status_by_apple_id

    def query_app_status(self, apple_id: int, verbose: bool = False) -> Optional[Dict[str, Any]]:
        """
        使用 Apple Lookup API (iTunes Search API) 查询应用状态
        """
        status_by_apple_id = self.query_app_statuses([str(apple_id)], verbose=verbose)
        return status_by_apple_id.get(str(apple_id), self._build_offline_status())
