"""左右資料樹之間的獨立內容結果區，兼作可拖曳分隔。"""
from PySide6.QtCore import Qt, QEvent, QPoint, QRect
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QSplitter, QSplitterHandle, QToolTip


def content_result(row):
    if row is None or row.directory or not row.verified: return '', '#000000', '尚未檢查內容'
    return ('=', '#000000', '內容相同') if row.status == 'same' else ('≠', '#e00000', '內容不同')


class ComparisonSplitter(QSplitter):
    def __init__(self, tree):
        super().__init__(Qt.Horizontal)
        self.tree = tree
        self.setHandleWidth(27)
        self.setChildrenCollapsible(False)

    def createHandle(self):
        return ResultGutter(self)


class ResultGutter(QSplitterHandle):
    def __init__(self, splitter):
        super().__init__(Qt.Horizontal, splitter)
        self.tree = splitter.tree
        self.setAccessibleName('內容比較結果分隔區')

    def bind(self):
        self.tree.viewport().installEventFilter(self)
        self.tree.header().installEventFilter(self)
        self.tree.verticalScrollBar().valueChanged.connect(lambda *_: self.update())
        self.tree.expanded.connect(lambda *_: self.update())
        self.tree.collapsed.connect(lambda *_: self.update())
        self.tree.model().modelReset.connect(self.update)

    def eventFilter(self, watched, event):
        if watched is not self.tree.viewport() and watched is not self.tree.header():
            if event.type() in (QEvent.MouseButtonPress, QEvent.MouseMove, QEvent.MouseButtonRelease, QEvent.MouseButtonDblClick):
                event.accept()
                return True
        if event.type() in (QEvent.Paint, QEvent.Resize, QEvent.Show, QEvent.LayoutRequest): self.update()
        return super().eventFilter(watched, event)

    def visible_results(self):
        results = []
        viewport = self.tree.viewport()
        index = self.tree.indexAt(QPoint(0, 0))
        if index.isValid(): index = index.siblingAtColumn(0)
        while index.isValid():
            row_rect = self.tree.visualRect(index)
            if row_rect.top() >= viewport.height(): break
            row = index.data(Qt.UserRole)
            symbol, color, _ = content_result(row)
            if symbol and row_rect.bottom() >= 0:
                top = viewport.mapTo(self.parentWidget(), QPoint(0, row_rect.top())).y() - self.y()
                results.append((index.data(Qt.UserRole + 1), QRect(1, top, self.width() - 2, row_rect.height()), symbol, color))
            index = self.tree.indexBelow(index)
        return results

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor('#f4f4f4'))
        painter.setPen(QColor('#c6c6c6'))
        painter.drawLine(0, 0, 0, self.height())
        painter.drawLine(self.width() - 1, 0, self.width() - 1, self.height())
        viewport = self.tree.viewport()
        top = viewport.mapTo(self.parentWidget(), QPoint(0, 0)).y() - self.y()
        painter.setClipRect(QRect(1, top, self.width() - 2, viewport.height()))
        painter.setFont(self.tree.font())
        for name, rect, symbol, color in self.visible_results():
            painter.setPen(QColor(color))
            painter.drawText(rect, Qt.AlignCenter, symbol)

    def event(self, event):
        if event.type() == QEvent.ToolTip:
            for name, rect, symbol, color in self.visible_results():
                if rect.contains(event.pos()):
                    QToolTip.showText(event.globalPos(), '內容相同' if symbol == '=' else '內容不同', self)
                    return True
            QToolTip.hideText()
            return True
        return super().event(event)
