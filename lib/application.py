"""應用程式啟動與跨程序比較請求入口。"""
from pathlib import Path
import sys
from PySide6.QtWidgets import QApplication
from lib.ui.main_window import MainWindow
from lib.ui.theme import APP_STYLE, apply_light_palette
from lib.ui.ui_common import msgCritical


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    apply_light_palette(app)
    app.setStyleSheet(APP_STYLE)
    from lib.integration.single_instance import InstanceChannel
    import os
    channel = InstanceChannel(Path(os.environ['LOCALAPPDATA']) / 'DualMirror', app)
    paths = [str(Path(path).resolve()) for path in sys.argv[1:]] if len(sys.argv) == 3 else []
    try:
        if not channel.start():
            if channel.forward(paths): return 0
            msgCritical('無法開啟比較', '無法將比較工作傳送至已開啟的 DualMirror，請確認原視窗狀態後再試。')
            return 1
        window = MainWindow(); window.showMaximized()
        channel.requested.connect(window.open_request)
        if paths: window.open_startup_pair(paths)
        return app.exec()
    finally:
        channel.close()
