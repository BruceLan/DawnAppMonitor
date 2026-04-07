"""
日志工具模块
提供 GitHub Actions 兼容的日志输出功能
"""
import os
from datetime import datetime


def is_github_actions() -> bool:
    """检查是否在 GitHub Actions 环境中运行"""
    return os.getenv('GITHUB_ACTIONS') == 'true'


def log_group(title: str):
    """开始一个可折叠的日志组"""
    if is_github_actions():
        print(f"::group::{title}")
    else:
        print(f"\n{'='*60}")
        print(f"{title}")
        print(f"{'='*60}")


def log_endgroup():
    """结束日志组"""
    if is_github_actions():
        print("::endgroup::")


def log_info(message: str):
    """输出信息日志"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"[{timestamp}] {message}")


def log_warning(message: str):
    """输出警告日志"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    if is_github_actions():
        print(f"::warning::{message}")
    print(f"[{timestamp}] ⚠️  {message}")


def log_error(message: str):
    """输出错误日志"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    if is_github_actions():
        print(f"::error::{message}")
    print(f"[{timestamp}] ❌ {message}")


def log_success(message: str):
    """输出成功日志"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    if is_github_actions():
        print(f"::notice::{message}")
    print(f"[{timestamp}] ✅ {message}")
