"""
VideoSlim 控制层

负责界面与服务的装配，以及压缩任务线程的生命周期管理。
"""

from src.controller.app import App
from src.controller.task import TaskRunner

__all__ = ["App", "TaskRunner"]
