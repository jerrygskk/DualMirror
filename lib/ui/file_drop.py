"""主視窗的檔案拖放；攔截檔案網址，避免落入文字編輯器。"""
from pathlib import Path

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QApplication, QWidget

from lib.ui.hex_compare import HexCompare
from lib.ui.text_compare import TextCompare


class FileDropFilter(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        window.setAcceptDrops(True)
        QApplication.instance().installEventFilter(self)

    def eventFilter(self, target, event):
        if event.type() not in (QEvent.DragEnter, QEvent.DragMove, QEvent.Drop): return False
        if not isinstance(target, QWidget) or target.window() is not self.window: return False
        mime = event.mimeData()
        if not mime.hasUrls(): return False
        event.ignore()
        window = self.window
        if window._closing or QApplication.activeModalWidget() is not None: return True
        urls = mime.urls()
        if len(urls) not in (1, 2) or not all(url.isLocalFile() for url in urls): return True
        paths = tuple(Path(url.toLocalFile()).resolve() for url in urls)
        if not all(path.is_file() for path in paths): return True
        if len(paths) == 2:
            if paths[0] == paths[1]: return True
            if event.type() == QEvent.Drop: window.open_file_pair(paths)
        else:
            page = window.tabs.currentWidget()
            if not isinstance(page, (TextCompare, HexCompare)): return True
            position = target.mapToGlobal(event.position().toPoint())
            views = (page.left_edit, page.right_edit) if isinstance(page, TextCompare) else page.views
            side = next((side for side, view in enumerate(views)
                         if view.parentWidget().rect().contains(view.parentWidget().mapFromGlobal(position))), None)
            if side is None: return True
            if event.type() == QEvent.Drop:
                window.replace_comparison_path(page, side, paths[0])
        event.setDropAction(Qt.CopyAction)
        event.accept()
        return True
