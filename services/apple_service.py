"""
Apple Store API 服务模块
"""
import requests
import json
from typing import Optional, Dict, Any, List
from utils.logger import log_info, log_warning, log_success, log_error


class AppleStoreService:
    """Apple Store API 服务类"""

    LOOKUP_BATCH_SIZE = 50

    def __init__(self):
        self.api_url = "https://itunes.apple.com/lookup"

    @staticmethod
    def _build_offline_status() -> Dict[str, Any]:
        return {
            'is_online': False,
            'version': None,
            'track_name': None,
            'release_date': None,
            'current_version_release_date': None
        }

    @staticmethod
    def _build_app_info(result: Dict[str, Any]) -> Dict[str, Any]:
        return {
            'is_online': True,
            'version': result.get('version'),
            'track_name': result.get('trackName'),
            'release_date': result.get('releaseDate'),
            'current_version_release_date': result.get('currentVersionReleaseDate'),
            'bundle_id': result.get('bundleId'),
            'track_view_url': result.get('trackViewUrl')
        }

    def query_app_statuses(
        self, apple_ids: List[str], verbose: bool = False
    ) -> Optional[Dict[str, Dict[str, Any]]]:
        """
        批量查询多个 Apple 应用状态，返回按 Apple ID 建立的映射
        """
        unique_apple_ids = list(dict.fromkeys(str(apple_id) for apple_id in apple_ids if str(apple_id).strip()))
        if not unique_apple_ids:
            return {}
        status_by_apple_id = {
            apple_id: self._build_offline_status()
            for apple_id in unique_apple_ids
        }

        try:
            for index in range(0, len(unique_apple_ids), self.LOOKUP_BATCH_SIZE):
                batch_apple_ids = unique_apple_ids[index:index + self.LOOKUP_BATCH_SIZE]
                params = {
                    'id': ','.join(batch_apple_ids),
                    'country': 'us'
                }

                if verbose:
                    log_info(f"🔍 批量查询 Apple 应用状态，Apple IDs: {params['id']}")
                    log_info(f"  API URL: {self.api_url}")
                    log_info(f"  参数: {params}")

                response = requests.get(self.api_url, params=params, timeout=10)
                response.raise_for_status()

                data = response.json()

                for result in data.get('results', []):
                    track_id = result.get('trackId')
                    if track_id is None:
                        continue
                    status_by_apple_id[str(track_id)] = self._build_app_info(result)

            if verbose:
                missing_ids = [
                    apple_id
                    for apple_id, status in status_by_apple_id.items()
                    if not status['is_online']
                ]
                for apple_id in missing_ids:
                    log_warning(f"未找到应用信息（Apple ID: {apple_id}）")

            return status_by_apple_id

        except requests.exceptions.RequestException as e:
            log_error(f"请求失败: {str(e)}")
            return None
        except json.JSONDecodeError as e:
            log_error(f"JSON 解析失败: {str(e)}")
            return None
        except Exception as e:
            log_error(f"查询异常: {str(e)}")
            return None

    def query_app_status(self, apple_id: int, verbose: bool = False) -> Optional[Dict[str, Any]]:
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
        status_by_apple_id = self.query_app_statuses([str(apple_id)], verbose=verbose)
        if status_by_apple_id is None:
            return None
        return status_by_apple_id.get(str(apple_id), self._build_offline_status())
