#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
VideoSlim - A video compression application using x264
"""

import datetime
import logging
import os
import sys

from PySide6 import QtWidgets

from src import meta
from src.app import App
from src.controller import Controller
from src.service import init_services
from src.view_qt import MainWindow


def setup_logging():
    """
    配置日志记录功能

    每次启动都会在 log 文件夹下生成一个以当前时间戳命名的日志文件，
    便于区分不同次运行产生的日志。
    """
    os.makedirs(meta.LOG_DIR, exist_ok=True)
    log_file_path = os.path.join(
        meta.LOG_DIR,
        datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + ".log",
    )

    logging.basicConfig(
        level=logging.DEBUG,
        filename=log_file_path,
        filemode="w",
        format="%(asctime)s - %(levelname)s - %(message)s",
        encoding="utf-8",
    )


def main():
    """应用程序的主入口"""
    setup_logging()

    init_services()

    app = QtWidgets.QApplication([])
    app.setApplicationName("VideoSlim")

    window = MainWindow()
    App(window, Controller())
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
