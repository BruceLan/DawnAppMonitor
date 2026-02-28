"""
飞书多维表格数据模型
用于映射和存储从飞书多维表格读取的记录数据
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
from packaging import version


@dataclass
class FileInfo:
    """文件信息模型"""
    file_token: str
    name: str
    size: int
    tmp_url: str
    type: str
    url: str


@dataclass
class LinkInfo:
    """链接信息模型"""
    link: str
    text: str


@dataclass
class UserInfo:
    """用户信息模型"""
    email: str
    en_name: str
    id: str
    name: str
    avatar_url: Optional[str] = None


@dataclass
class ParentRecord:
    """父记录引用模型"""
    table_id: str
    record_ids: Optional[List[str]] = None
    text: Optional[str] = None
    text_arr: Optional[List[str]] = None
    type: str = "text"


@dataclass
class ApplePackageRecord:
    """Apple 包记录模型"""
    # 基础信息
    apple_id: Optional[int] = None
    package_name: Optional[str] = None  # 包名
    package_status: Optional[str] = None  # 包状态
    version: Optional[str] = None  # 版本号
    test_package_name: Optional[str] = None  # 测试包名
    production_package_name: Optional[str] = None  # 生产包名
    package_size: Optional[str] = None  # 包Size
    
    # 文件信息
    logo: Optional[List[FileInfo]] = None
    
    # 链接信息
    repository_url: Optional[LinkInfo] = None  # 仓库地址
    
    # 业务信息
    product_code: Optional[str] = None  # 商品code
    team: Optional[str] = None  # 团队
    quarter: Optional[str] = None  # 所属季度
    stage: Optional[str] = None  # 阶段
    
    # 人员信息
    developers: Optional[List[UserInfo]] = None  # 开发人员
    designers: Optional[List[UserInfo]] = None  # 设计人员
    package_sender: Optional[List[UserInfo]] = None  # 发包人员
    
    # 时间信息
    submission_time: Optional[int] = None  # 提审时间（时间戳）
    approval_time: Optional[int] = None  # 过审时间（时间戳）
    status_update_time: Optional[int] = None  # 包状态更新时间（时间戳）
    exception_time: Optional[int] = None  # 异常时间（时间戳）
    
    # 其他信息
    af_aj_info: Optional[str] = None  # 是否申请AF/AJ
    machine_location: Optional[str] = None  # 机器位置
    development_days: Optional[float] = None  # 开发人日
    application_topic: Optional[str] = None  # 应用选题
    exception_category: Optional[str] = None  # 异常类别
    refund_callback_url: Optional[str] = None  # 退款回调地址
    privacy_policy: Optional[str] = None  # 隐私协议
    update_description: Optional[str] = None  # 更新文案
    notes: Optional[str] = None  # 备注
    
    # 关联信息
    parent_record: Optional[List[ParentRecord]] = None  # 父记录
    record_id: Optional[str] = None  # 记录ID
    children: List['ApplePackageRecord'] = field(default_factory=list)  # 子记录列表（版本记录）
    
    @classmethod
    def from_feishu_fields(cls, fields: Dict[str, Any], record_id: Optional[str] = None) -> 'ApplePackageRecord':
        """
        从飞书字段字典创建模型实例
        
        Args:
            fields: 飞书多维表格的字段字典
            record_id: 记录ID
        
        Returns:
            ApplePackageRecord 实例
        """
        # 处理文件信息
        logo = None
        if 'logo' in fields and fields['logo']:
            logo = [FileInfo(**item) if isinstance(item, dict) else item for item in fields['logo']]
        
        # 处理链接信息
        repository_url = None
        if '仓库地址' in fields and fields['仓库地址']:
            repo_data = fields['仓库地址']
            if isinstance(repo_data, dict):
                repository_url = LinkInfo(**repo_data)
            else:
                repository_url = LinkInfo(link=str(repo_data), text=str(repo_data))
        
        # 处理用户信息
        def parse_user_list(field_name: str) -> Optional[List[UserInfo]]:
            if field_name not in fields or not fields[field_name]:
                return None
            users = fields[field_name]
            if isinstance(users, list):
                return [UserInfo(**user) if isinstance(user, dict) else user for user in users]
            return None
        
        developers = parse_user_list('开发人员')
        designers = parse_user_list('设计人员')
        package_sender = parse_user_list('发包人员')
        
        # 处理父记录
        parent_record = None
        if '父记录' in fields and fields['父记录']:
            parent_data = fields['父记录']
            if isinstance(parent_data, list):
                parent_record = []
                for item in parent_data:
                    if isinstance(item, dict):
                        parent_record.append(ParentRecord(**item))
                    else:
                        parent_record.append(item)
        
        # 处理时间戳字段（转换为整数）
        def parse_timestamp(field_name: str) -> Optional[int]:
            if field_name not in fields or not fields[field_name]:
                return None
            value = fields[field_name]
            if isinstance(value, (int, float)):
                return int(value)
            if isinstance(value, str):
                try:
                    return int(float(value))
                except (ValueError, TypeError):
                    return None
            return None
        
        return cls(
            record_id=record_id,
            apple_id=fields.get('Apple ID'),
            package_name=fields.get('包名'),
            package_status=fields.get('包状态'),
            version=fields.get('版本号'),
            test_package_name=fields.get('测试包名'),
            production_package_name=fields.get('生产包名'),
            package_size=fields.get('包Size'),
            logo=logo,
            repository_url=repository_url,
            product_code=fields.get('商品code'),
            team=fields.get('团队'),
            quarter=fields.get('所属季度'),
            stage=fields.get('阶段'),
            developers=developers,
            designers=designers,
            package_sender=package_sender,
            submission_time=parse_timestamp('提审时间'),
            approval_time=parse_timestamp('过审时间'),
            status_update_time=parse_timestamp('包状态更新时间'),
            exception_time=parse_timestamp('异常时间'),
            af_aj_info=fields.get('是否申请AF/AJ'),
            machine_location=fields.get('机器位置'),
            development_days=fields.get('开发人日'),
            application_topic=fields.get('应用选题'),
            exception_category=fields.get('异常类别'),
            refund_callback_url=fields.get('退款回调地址'),
            privacy_policy=fields.get('隐私协议'),
            update_description=fields.get('更新文案'),
            notes=fields.get('备注'),
            parent_record=parent_record
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        result = {}
        for key, value in self.__dict__.items():
            if value is None:
                continue
            if isinstance(value, list):
                result[key] = [item.__dict__ if hasattr(item, '__dict__') else item for item in value]
            elif hasattr(value, '__dict__'):
                result[key] = value.__dict__
            else:
                result[key] = value
        return result
    
    def get_submission_datetime(self) -> Optional[datetime]:
        """获取提审时间的 datetime 对象"""
        if self.submission_time:
            return datetime.fromtimestamp(self.submission_time / 1000)
        return None
    
    def get_approval_datetime(self) -> Optional[datetime]:
        """获取过审时间的 datetime 对象"""
        if self.approval_time:
            return datetime.fromtimestamp(self.approval_time / 1000)
        return None
    
    def get_latest_version(self) -> Optional[str]:
        """
        获取最新版本号
        
        规则：
        1. 如果没有子记录，最新版本为：版本号
        2. 如果有子记录，最新版本为：版本号最大的那条子记录的版本号
        
        Returns:
            最新版本号
        """
        if not self.children:
            # 没有子记录，返回自己的版本号
            return self.version
        
        # 有子记录，找到版本号最大的子记录
        latest_child = None
        latest_version = None
        
        for child in self.children:
            if not child.version:
                continue
            
            try:
                # 使用 packaging.version 进行版本号比较
                child_version = version.parse(child.version)
                
                if latest_version is None or child_version > latest_version:
                    latest_version = child_version
                    latest_child = child
            except Exception:
                # 如果版本号格式不规范，跳过该子记录
                continue
        
        # 如果找到了有效版本号的子记录，返回其版本号
        if latest_child and latest_child.version:
            return latest_child.version
        
        # 如果没有找到有效版本号的子记录，返回自己的版本号
        return self.version

    def validate_data(self) -> Dict[str, Any]:
        """
        验证记录数据的完整性

        Returns:
            验证结果字典：
            {
                'is_valid': bool,  # 是否有效
                'errors': List[str]  # 错误信息列表
            }
        """
        errors = []

        if not self.children:
            # 没有子记录的情况
            if not self.version:
                errors.append("缺少版本号")
            if not self.submission_time:
                errors.append("缺少提审时间")
        else:
            # 有子记录的情况
            # 检查是否所有子记录都没有版本号
            versions_with_value = [child.version for child in self.children if child.version]
            if not versions_with_value:
                errors.append(f"所有子记录（共{len(self.children)}条）都缺少版本号")
            else:
                # 检查是否有重复的版本号
                version_counts = {}
                for child in self.children:
                    if child.version:
                        version_counts[child.version] = version_counts.get(child.version, 0) + 1

                duplicate_versions = {v: count for v, count in version_counts.items() if count > 1}
                if duplicate_versions:
                    for ver, count in duplicate_versions.items():
                        errors.append(f"{count}条子记录版本号相同 ({ver})")

            # 检查是否所有子记录都没有提审时间
            submission_times_with_value = [child.submission_time for child in self.children if child.submission_time]
            if not submission_times_with_value:
                errors.append(f"所有子记录（共{len(self.children)}条）都缺少提审时间")

        return {
            'is_valid': len(errors) == 0,
            'errors': errors
        }

