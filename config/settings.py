"""
配置管理模块
"""
import os
from typing import List, Dict, Any
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()


class Settings:
    """应用配置类"""

    def __init__(self):
        # 环境标识：local（本地调试）或 production（生产环境）
        self.ENV = os.getenv("ENV", "production")

        # 飞书应用配置
        self.FEISHU_APP_ID = os.getenv("FEISHU_APP_ID")
        self.FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET")
        self.FEISHU_WIKI_URL = os.getenv("FEISHU_WIKI_URL")
        self.FEISHU_MESSAGE_PREFIX = os.getenv("FEISHU_MESSAGE_PREFIX", "").strip()
        self.ENABLE_RECORD_REVIEW = self._get_bool_env("ENABLE_RECORD_REVIEW", False)

        # 飞书通知配置
        self.FEISHU_NOTIFICATIONS = self._load_notifications()

    @staticmethod
    def _get_bool_env(key: str, default: bool = False) -> bool:
        """解析布尔环境变量，未配置时返回默认值"""
        value = os.getenv(key)
        if value is None:
            return default

        return value.strip().lower() in {"1", "true", "yes", "on"}

    def _load_notifications(self) -> List[Dict[str, Any]]:
        """
        加载飞书通知配置

        本地调试模式（ENV=local）：
        - 不发送通知，返回空列表

        生产环境（ENV=production）：
        - 从环境变量加载通知配置
        """
        # 本地调试模式：不发送通知
        if self.ENV == "local":
            return []

        # 生产环境：从环境变量加载配置
        notifications = []

        # 添加 @所有人 的群
        chat_id_all = os.getenv("FEISHU_CHAT_ID_ALL")
        if chat_id_all:
            notifications.append({
                "chat_id": chat_id_all,
                "mention_all": True
            })

        # 添加 @指定用户 的群
        chat_id_team = os.getenv("FEISHU_CHAT_ID_TEAM")
        mention_users_str = os.getenv("FEISHU_MENTION_USERS")

        if chat_id_team and mention_users_str:
            mention_user_ids = [uid.strip() for uid in mention_users_str.split(",") if uid.strip()]
            if mention_user_ids:
                notifications.append({
                    "chat_id": chat_id_team,
                    "mention_user_ids": mention_user_ids
                })

        return notifications

    def validate(self) -> bool:
        """验证必要的配置是否存在"""
        if not self.FEISHU_APP_ID:
            return False
        if not self.FEISHU_APP_SECRET:
            return False
        if not self.FEISHU_WIKI_URL:
            return False
        return True


# 全局配置实例
settings = Settings()
