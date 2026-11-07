#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
VideoSlim 应用入口。
"""

import datetime
import logging
import os
import sys

from PySide6 import QtWidgets

from src import meta
from src.controller.app import App
from src.service import init_services
from src.view import MainWindow


def setup_logging():
    """每次启动生成一个以时间戳命名的日志文件，便于区分不同次运行"""
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
    App(window)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
