import logging
from typing import Optional

import requests

from src import meta
from src.model.message import UpdateMessage
from src.service.message import MessageService


class UpdateService:
    """
    更新服务类，用于检查应用程序的新版本更新

    该类采用单例模式实现，提供了检查新版本的功能，
    并在发现新版本时通过消息服务发送更新通知。
    """

    _instance: Optional["UpdateService"] = None

    def __init__(self):
        """
        初始化更新服务实例

        Raises:
            ValueError: 当尝试创建多个UpdateService实例时抛出
        """
        if UpdateService._instance is not None:
            raise ValueError("UpdateService already initialized")
        UpdateService._instance = self

    @staticmethod
    def get_instance() -> "UpdateService":
        """
        获取更新服务的单例实例

        Returns:
            UpdateService: 更新服务的单例实例

        该方法采用懒加载模式，只有在第一次调用时才会创建UpdateService实例。
        """
        if UpdateService._instance is None:
            UpdateService._instance = UpdateService()

        return UpdateService._instance

    @staticmethod
    def check_for_updates() -> bool:
        """
        检查是否有新版本更新

        该方法会：
        1. 从配置的更新检查URL获取最新版本信息
        2. 比较当前版本与最新版本
        3. 如果发现新版本，通过消息服务发送更新通知
        4. 记录检查过程中的异常信息

        使用requests库发送HTTP请求获取最新版本信息，
        超时时间设置为10秒。如果检查失败，会记录警告日志。

        Returns:
            bool: 发现新版本时返回 True；已是最新或检查失败时返回 False
        """
        message_service = MessageService.get_instance()
        try:
            response = requests.get(meta.CHECK_UPDATE_URL, timeout=10)
            data = response.json()

            if data and len(data) > 0:
                latest_release = data[0]
                if UpdateService.is_new_version(
                    meta.VERSION, latest_release["tag_name"]
                ):
                    message_service.send_message(UpdateMessage())
                    return True
            return False
        except Exception as e:
            logging.warning(f"检查更新失败: {e}")
            return False

    @staticmethod
    def is_new_version(current_version: str, latest_version: str) -> bool:
        """
        检查是否有新版本更新

        Args:
            current_version (str): 当前应用程序版本号
            latest_version (str): 最新版本号

        Returns:
            bool: 如果有新版本则返回True，否则返回False
        """
        # 移除版本号前缀（如"v"）
        current_version = current_version.lstrip("v")
        latest_version = latest_version.lstrip("v")

        # 移除版本号中的预发布标签（如"-alpha"）
        current_version = current_version.split("-")[0]
        latest_version = latest_version.split("-")[0]

        # 按点分隔版本号
        current_parts = current_version.split(".")
        latest_parts = latest_version.split(".")

        # 比较每个部分的数值
        for i in range(min(len(current_parts), len(latest_parts))):
            if int(latest_parts[i]) > int(current_parts[i]):
                return True
            elif int(latest_parts[i]) < int(current_parts[i]):
                return False

        # 如果所有部分都相等，且最新版本号更长，则为新版本
        return len(latest_parts) > len(current_parts)
