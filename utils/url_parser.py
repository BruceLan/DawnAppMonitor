"""
URL 解析工具模块
"""
from typing import Optional, Tuple
from utils.logger import log_error


def parse_wiki_url(url: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    解析 wiki URL，提取节点 token、table_id 和 view_id
    
    Args:
        url: wiki URL
    
    Returns:
        (wiki_node_token, table_id, view_id) 元组
    """
    try:
        # 从 URL 中提取 wiki 节点 token
        # 格式: https://xxx.feishu.cn/wiki/NODE_TOKEN?table=TABLE_ID&view=VIEW_ID
        if "/wiki/" in url:
            parts = url.split("/wiki/")[1].split("?")[0]
            wiki_node_token = parts
            
            # 提取 table_id 和 view_id
            table_id = None
            view_id = None
            if "?" in url:
                params = url.split("?")[1]
                for param in params.split("&"):
                    if param.startswith("table="):
                        table_id = param.split("=")[1]
                    elif param.startswith("view="):
                        view_id = param.split("=")[1]
            
            return wiki_node_token, table_id, view_id
    except Exception as e:
        log_error(f"解析 URL 失败: {str(e)}")
    
    return None, None, None
