import logging
import threading
from typing import Optional

from src.model.video import Task, TaskInfo
from src.service.video import VideoService


class TaskRunner:
    """压缩任务的后台线程封装"""

    def __init__(self) -> None:
        self._thread: Optional[threading.Thread] = None

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(
        self,
        *,
        config_name: str,
        delete_audio: bool,
        delete_source: bool,
        file_paths: list[str],
        recurse: bool,
    ) -> None:
        """
        创建压缩任务并在后台线程中执行

        Args:
            config_name: 要使用的压缩配置名称
            delete_audio: 是否删除视频中的音频轨道
            delete_source: 压缩完成后是否删除源文件
            file_paths: 要压缩的视频文件路径列表
            recurse: 如果路径是目录，是否递归处理其中的所有视频文件
        """

        task = Task(
            info=TaskInfo(
                targets=file_paths,
                process_config_name=config_name,
                delete_audio=delete_audio,
                delete_source=delete_source,
                recursive=recurse,
            ),
        )

        self._thread = threading.Thread(
            target=VideoService.process_task,
            args=(task,),
        )
        self._thread.start()

    def stop(self) -> None:
        """
        终止当前压缩任务

        终止正在执行的 ffmpeg 子进程，并阻止任务继续处理列表中后续的文件。
        未在压缩时调用不会产生副作用。
        """

        logging.info("收到终止请求")
        VideoService.get_instance().stop_process()
