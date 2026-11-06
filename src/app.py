"""
应用装配层：把界面、控制器和服务接起来。
"""

import logging
import os
import threading

from PySide6 import QtCore, QtWidgets

from src.controller import Controller
from src.model import message
from src.service.message import MessageService
from src.service.updater import UpdateService
from src.view_qt import MainWindow


class App(QtCore.QObject):
    # 检查更新跑在后台线程，结果经信号回到界面线程
    update_checked = QtCore.Signal(bool)

    # 消息队列轮询间隔（毫秒）
    MESSAGE_POLL_INTERVAL = 100

    def __init__(self, window: MainWindow, controller: Controller) -> None:
        super().__init__(window)

        self.window = window
        self.controller = controller

        # 防止消息框里的嵌套事件循环重复进入轮询
        self._polling = False
        self._closed = False

        self._connect_signals()

        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(self.MESSAGE_POLL_INTERVAL)
        self._timer.timeout.connect(self._poll_messages)
        self._timer.start()

    def _connect_signals(self) -> None:
        self.window.start_requested.connect(self._on_start)
        self.window.stop_requested.connect(self._on_stop)
        self.window.update_check_requested.connect(self._on_check_update)
        self.window.close_requested.connect(self._on_close)
        self.window.close_guard = self._confirm_close
        self.update_checked.connect(self._on_update_checked)

    def _on_start(self) -> None:
        if self.controller.is_task_running():
            return

        config_name = self.window.current_config_name()
        if not config_name:
            self.window.show_warning("提示", "没有可用的参数配置，请检查 config.json")
            return

        file_paths = self.window.file_paths()
        if not file_paths:
            self.window.show_warning("提示", "请先拖拽文件到此处")
            return

        self.window.reset_progress()
        self.window.set_running(True)
        self.window.set_status(f"共 {len(file_paths)} 个目标，正在解析视频…")

        try:
            self.controller.compression(
                config_name=config_name,
                delete_audio=self.window.delete_audio_enabled(),
                delete_source=self.window.delete_source_enabled(),
                file_paths=file_paths,
                recurse=self.window.recurse_enabled(),
            )
        except Exception as e:
            logging.exception("启动压缩任务失败")
            self.window.set_running(False)
            self.window.show_error("错误", f"启动压缩任务失败：{e}")

    def _on_stop(self) -> None:
        if not self.controller.is_task_running():
            self.window.set_running(False)
            return

        if not self.window.ask_confirm("确认", "确定要终止当前的压缩任务吗？"):
            return

        self.window.set_status("正在终止压缩任务…")
        self.controller.terminate()
        self.window.set_running(False)

    def _on_check_update(self) -> None:
        self.window.set_status("正在检查更新…")
        threading.Thread(target=self._check_update_in_background, daemon=True).start()

    def _check_update_in_background(self) -> None:
        self.update_checked.emit(bool(UpdateService.check_for_updates()))

    @QtCore.Slot(bool)
    def _on_update_checked(self, has_update: bool) -> None:
        if has_update:
            self.window.set_status("发现新版本，请前往项目主页下载")
        else:
            self.window.set_status("当前已是最新版本")

    def _confirm_close(self) -> bool:
        if not self.controller.is_task_running():
            return True

        return self.window.ask_confirm("确认", "当前有正在处理的任务，是否关闭程序？")

    def _on_close(self) -> None:
        if self._closed:
            return

        self._closed = True
        self._timer.stop()
        logging.info("窗口关闭，开始收尾")
        self.controller.close()

    def _poll_messages(self) -> None:
        if self._polling:
            return

        self._polling = True
        try:
            self._drain_messages()
        finally:
            self._polling = False

        # 兜底同步：任务线程自己结束时不一定还有消息可刷
        self.window.set_running(self.controller.is_task_running())

    def _drain_messages(self) -> None:
        service = MessageService.get_instance()

        while not self._closed:
            msg = service.try_receive_message()
            if msg is None:
                return

            self._handle_message(msg)

    def _handle_message(self, msg: message.IMessage) -> None:
        window = self.window

        match msg:
            case message.WarningMessage(title=title, message=text):
                window.show_warning(title, text)

            case message.ErrorMessage(title=title, message=text):
                window.show_error(title, text)

            case message.CompressionErrorMessage(title=title, message=text):
                window.set_status("处理过程中出现错误")
                window.show_error(title, text)

            case message.UpdateMessage():
                window.set_status("发现新版本，请前往项目主页下载")
                window.show_info("更新提示", "有新版本可用，请前往项目主页更新")

            case message.ConfigLoadMessage(config_names=config_names):
                window.set_config_names(config_names)

            case message.CompressionStartMessage(total=total):
                window.reset_progress()
                window.set_total_progress(0, total)
                window.set_running(True)
                window.set_status(f"开始压缩，共 {total} 个文件")

            case message.CompressionCurrentProgressMessage(
                file_name=_, current=current, total=total
            ):
                # 这里的 current / total 是秒数
                if total > 0:
                    window.set_current_progress(current / total)

            case message.CompressionTotalProgressMessage(
                current=current, total=total, file_name=file_name
            ):
                window.set_current_progress(0)
                window.set_total_progress(current, total)
                window.set_status(
                    f"[{current}/{total}] 正在处理：{os.path.basename(file_name)}"
                )

            case message.CompressionFinishedMessage(total=total):
                window.set_current_progress(0)
                window.set_total_progress(total, total)
                window.set_running(False)
                window.set_status(f"处理完成！已经处理 {total} 个文件")
                window.show_info("提示", "转换结束")

            case message.CompressionStoppedMessage():
                window.set_current_progress(0)
                window.set_running(False)
                window.set_status("压缩任务已终止")
                window.show_info("提示", "已终止当前的压缩任务")

            case message.ExitMessage():
                self._on_close()
                app = QtWidgets.QApplication.instance()
                if app is not None:
                    app.quit()

            case _:
                logging.warning(f"未处理的消息类型: {type(msg).__name__}")
