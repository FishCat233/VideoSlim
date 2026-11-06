"""
VideoSlim 的界面。

用户操作统一以信号抛出，外部控制器 connect 后即可接管；界面状态由 set_* 方法写入。
"""

import os
from typing import Callable, Optional

from PySide6 import QtCore, QtGui, QtWidgets

from src import meta, utils


def local_paths(mime: QtCore.QMimeData) -> list[str]:
    if not mime.hasUrls():
        return []

    paths = [url.toLocalFile() for url in mime.urls() if url.isLocalFile()]
    return [path for path in paths if path]


class GithubLabel(QtWidgets.QLabel):
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__("github", parent)

        self.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("color: #9aa0a6;")
        self.setToolTip(meta.GITHUB_URL)

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            QtGui.QDesktopServices.openUrl(QtCore.QUrl(meta.GITHUB_URL))

        return super().mousePressEvent(event)


class FileListEdit(QtWidgets.QPlainTextEdit):
    """用户输入的文件路径，一行一个"""

    filesDropped = QtCore.Signal(list)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)

        self.setAcceptDrops(True)
        self.setPlaceholderText(
            "把视频文件或文件夹拖到窗口里，也可以直接粘贴路径（一行一个）"
        )
        self.setLineWrapMode(QtWidgets.QPlainTextEdit.LineWrapMode.NoWrap)
        self.setTabChangesFocus(True)

    def dragEnterEvent(self, event: QtGui.QDragEnterEvent) -> None:
        if local_paths(event.mimeData()):
            event.acceptProposedAction()

    def dragMoveEvent(self, event: QtGui.QDragMoveEvent) -> None:
        if local_paths(event.mimeData()):
            event.acceptProposedAction()

    def dropEvent(self, event: QtGui.QDropEvent) -> None:
        paths = local_paths(event.mimeData())
        if not paths:
            return

        self.append_files(paths)
        self.filesDropped.emit(paths)
        event.acceptProposedAction()

    def file_paths(self) -> list[str]:
        text = self.toPlainText()
        return [line.strip() for line in text.splitlines() if line.strip()]

    def append_files(self, paths: list[str]) -> None:
        if not paths:
            return

        if not self.toPlainText():
            self.setPlainText("\n".join(paths))
        else:
            for path in paths:
                self.appendPlainText(path)

        # 光标停在末尾，用户接着粘贴时不必再挪
        cursor = self.textCursor()
        cursor.movePosition(QtGui.QTextCursor.MoveOperation.End)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()

    def clear_files(self) -> None:
        self.clear()


class ProgressPanel(QtWidgets.QWidget):
    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)

        self.current_bar = QtWidgets.QProgressBar()
        self.current_bar.setRange(0, 100)
        self.current_bar.setFormat("%p%")
        self.current_bar.setMinimumHeight(18)

        self.total_bar = QtWidgets.QProgressBar()
        self.total_bar.setRange(0, 100)
        self.total_bar.setFormat("0/0")
        self.total_bar.setMinimumHeight(18)

        l_progress = QtWidgets.QGridLayout(self)
        l_progress.setContentsMargins(0, 0, 0, 0)
        l_progress.setHorizontalSpacing(8)
        l_progress.setVerticalSpacing(6)

        l_progress.addWidget(QtWidgets.QLabel("当前文件"), 0, 0)
        l_progress.addWidget(self.current_bar, 0, 1)
        l_progress.addWidget(QtWidgets.QLabel("总进度"), 1, 0)
        l_progress.addWidget(self.total_bar, 1, 1)

        l_progress.setColumnStretch(1, 1)

    def set_current_progress(self, value: float) -> None:
        value = min(max(value, 0.0), 1.0)
        self.current_bar.setValue(round(value * 100))

    def set_total_progress(self, current: int, total: int) -> None:
        if total <= 0:
            self.total_bar.setValue(0)
            self.total_bar.setFormat("0/0")
            return

        self.total_bar.setValue(round(current / total * 100))
        self.total_bar.setFormat(f"{current}/{total}")

    def reset(self) -> None:
        self.current_bar.setValue(0)
        self.total_bar.setValue(0)
        self.total_bar.setFormat("0/0")


class MainWindow(QtWidgets.QMainWindow):
    """VideoSlim 主窗口"""

    start_requested = QtCore.Signal()
    stop_requested = QtCore.Signal()
    clear_requested = QtCore.Signal()
    files_dropped = QtCore.Signal(list)
    config_changed = QtCore.Signal(str)
    recurse_changed = QtCore.Signal(bool)
    delete_source_changed = QtCore.Signal(bool)
    delete_audio_changed = QtCore.Signal(bool)
    update_check_requested = QtCore.Signal()
    close_requested = QtCore.Signal()

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)

        # 关闭前检查钩子：返回 False 则取消关闭，例如有任务在跑时弹窗确认。
        self.close_guard: Optional[Callable[[], bool]] = None

        self.setWindowTitle(f"VideoSlim 视频压缩 {meta.VERSION}")
        self.setWindowIcon(self._load_icon())
        self.setMinimumSize(560, 380)
        self.resize(620, 460)
        self.setAcceptDrops(True)

        self._build_menubar()

        self.w_main = QtWidgets.QWidget()
        self.l_main = QtWidgets.QVBoxLayout(self.w_main)
        self.l_main.setContentsMargins(16, 12, 16, 10)
        self.l_main.setSpacing(10)

        self._build_header()
        self._build_body()

        self.setCentralWidget(self.w_main)
        self._build_statusbar()

        self.reset_progress()
        self.set_running(False)
        self._center_on_screen()

    def _load_icon(self) -> QtGui.QIcon:
        icon_path = utils.get_path("./tools/icon.ico")
        if os.path.exists(icon_path):
            return QtGui.QIcon(icon_path)
        return QtGui.QIcon()

    def _center_on_screen(self) -> None:
        screen = QtGui.QGuiApplication.primaryScreen()
        if screen is None:
            return

        frame = self.frameGeometry()
        frame.moveCenter(screen.availableGeometry().center())
        self.move(frame.topLeft())

    def _build_menubar(self) -> None:
        menubar = self.menuBar()

        menu_action = menubar.addMenu("操作")

        self.action_start = menu_action.addAction("开始压缩")
        self.action_start.setShortcut(QtGui.QKeySequence("Ctrl+Return"))
        self.action_start.triggered.connect(lambda: self.start_requested.emit())

        self.action_stop = menu_action.addAction("中止")
        self.action_stop.setShortcut(QtGui.QKeySequence("Esc"))
        self.action_stop.triggered.connect(lambda: self.stop_requested.emit())

        self.action_clear = menu_action.addAction("清空列表")
        self.action_clear.setShortcut(QtGui.QKeySequence("Ctrl+L"))
        self.action_clear.triggered.connect(self.action_clear_list)

        menu_action.addSeparator()

        action_quit = menu_action.addAction("退出")
        action_quit.setShortcut(QtGui.QKeySequence("Ctrl+Q"))
        action_quit.triggered.connect(self.close)

        menu_settings = menubar.addMenu("设置")

        # 单选配置项由 set_config_names 运行时填充
        self.menu_config = menu_settings.addMenu("参数配置")
        self.config_group = QtGui.QActionGroup(self)
        self.config_group.setExclusive(True)
        self._build_config_placeholder()

        menu_settings.addSeparator()

        self.action_recursive = menu_settings.addAction("递归处理子文件夹")
        self.action_recursive.setCheckable(True)
        self.action_recursive.toggled.connect(
            lambda checked: self.recurse_changed.emit(checked)
        )

        self.action_delete_source = menu_settings.addAction("完成后删除旧文件")
        self.action_delete_source.setCheckable(True)
        self.action_delete_source.toggled.connect(
            lambda checked: self.delete_source_changed.emit(checked)
        )

        self.action_delete_audio = menu_settings.addAction("删除音频轨道")
        self.action_delete_audio.setCheckable(True)
        self.action_delete_audio.toggled.connect(
            lambda checked: self.delete_audio_changed.emit(checked)
        )

        menu_help = menubar.addMenu("帮助")

        action_home = menu_help.addAction("项目主页")
        action_home.triggered.connect(
            lambda: QtGui.QDesktopServices.openUrl(QtCore.QUrl(meta.GITHUB_URL))
        )

        action_update = menu_help.addAction("检查更新")
        action_update.triggered.connect(lambda: self.update_check_requested.emit())

        menu_help.addSeparator()

        action_about = menu_help.addAction("关于 VideoSlim")
        action_about.triggered.connect(self.show_about)

    def _build_header(self) -> None:
        w_header = QtWidgets.QWidget()
        l_header = QtWidgets.QHBoxLayout(w_header)
        l_header.setContentsMargins(0, 0, 0, 0)

        title_label = QtWidgets.QLabel("将视频拖拽到此窗口:")
        w_github = GithubLabel()

        l_header.addWidget(title_label)
        l_header.addStretch()
        l_header.addWidget(w_github)

        self.l_main.addWidget(w_header)

    def _build_body(self) -> None:
        self.file_list = FileListEdit()
        self.file_list.filesDropped.connect(
            lambda paths: self.files_dropped.emit(paths)
        )
        self.progress = ProgressPanel()

        self.l_main.addWidget(self.file_list, 1)
        self.l_main.addWidget(self.progress)

    def _build_statusbar(self) -> None:
        self.status_label = QtWidgets.QLabel("就绪")
        self.config_label = QtWidgets.QLabel()

        status_bar = self.statusBar()
        status_bar.addWidget(self.status_label, 1)
        status_bar.addPermanentWidget(self.config_label)

        self.set_config_indicator(None)

    def action_clear_list(self) -> None:
        self.file_list.clear_files()
        self.reset_progress()
        self.set_status("就绪")
        self.clear_requested.emit()

    def show_about(self) -> None:
        QtWidgets.QMessageBox.about(
            self,
            "关于 VideoSlim",
            f"<b>VideoSlim</b> {meta.VERSION}<br>"
            "简洁易用的 Windows 视频压缩工具<br><br>"
            f"<a href='{meta.GITHUB_URL}'>{meta.GITHUB_URL}</a>",
        )

    def _build_config_placeholder(self) -> None:
        self.menu_config.clear()

        action_placeholder = self.menu_config.addAction("（尚未加载配置）")
        action_placeholder.setEnabled(False)

    def set_config_names(self, names: list[str], current: Optional[str] = None) -> None:
        for action in self.config_group.actions():
            self.config_group.removeAction(action)
        self.menu_config.clear()

        if not names:
            self._build_config_placeholder()
            self.set_config_indicator(None)
            return

        for name in names:
            action = self.menu_config.addAction(name)
            action.setCheckable(True)
            action.setData(name)
            action.triggered.connect(
                lambda checked=False, name=name: self._on_config_selected(name)
            )
            self.config_group.addAction(action)

        selected = current if current in names else names[0]
        for action in self.config_group.actions():
            action.setChecked(action.data() == selected)

        self.set_config_indicator(selected)

    def _on_config_selected(self, name: str) -> None:
        self.set_config_indicator(name)
        self.config_changed.emit(name)

    def current_config_name(self) -> Optional[str]:
        for action in self.config_group.actions():
            if action.isChecked():
                return action.data()
        return None

    def set_config_indicator(self, name: Optional[str]) -> None:
        self.config_label.setText(f"配置：{name}" if name else "配置：无")

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)
        self.status_label.setToolTip(text)

    def set_running(self, running: bool) -> None:
        self.action_start.setEnabled(not running)
        self.action_stop.setEnabled(running)
        self.action_clear.setEnabled(not running)
        self.file_list.setReadOnly(running)

    def recurse_enabled(self) -> bool:
        return self.action_recursive.isChecked()

    def delete_source_enabled(self) -> bool:
        return self.action_delete_source.isChecked()

    def delete_audio_enabled(self) -> bool:
        return self.action_delete_audio.isChecked()

    def set_current_progress(self, value: float) -> None:
        self.progress.set_current_progress(value)

    def set_total_progress(self, current: int, total: int) -> None:
        self.progress.set_total_progress(current, total)

    def reset_progress(self) -> None:
        self.progress.reset()

    def file_paths(self) -> list[str]:
        return self.file_list.file_paths()

    def add_files(self, paths: list[str]) -> None:
        self.file_list.append_files(paths)

    def dragEnterEvent(self, event: QtGui.QDragEnterEvent) -> None:
        """拖到文件列表以外的空白处也能接收文件"""
        if local_paths(event.mimeData()):
            event.acceptProposedAction()

    def dragMoveEvent(self, event: QtGui.QDragMoveEvent) -> None:
        if local_paths(event.mimeData()):
            event.acceptProposedAction()

    def dropEvent(self, event: QtGui.QDropEvent) -> None:
        paths = local_paths(event.mimeData())
        if not paths:
            return

        self.add_files(paths)
        self.files_dropped.emit(paths)
        event.acceptProposedAction()

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        if self.close_guard is not None and not self.close_guard():
            event.ignore()
            return

        self.close_requested.emit()
        event.accept()

    def show_warning(self, title: str, text: str) -> None:
        QtWidgets.QMessageBox.warning(self, title, text)

    def show_error(self, title: str, text: str) -> None:
        QtWidgets.QMessageBox.critical(self, title, text)

    def show_info(self, title: str, text: str) -> None:
        QtWidgets.QMessageBox.information(self, title, text)

    def ask_confirm(self, title: str, text: str) -> bool:
        answer = QtWidgets.QMessageBox.question(
            self,
            title,
            text,
            QtWidgets.QMessageBox.StandardButton.Yes
            | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No,
        )
        return answer == QtWidgets.QMessageBox.StandardButton.Yes
