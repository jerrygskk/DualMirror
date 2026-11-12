"""唯讀十六進位雙欄比較，僅為可見列產生顯示文字。"""
from pathlib import Path
from bisect import bisect_right
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, Signal, QRect
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableView, QSplitter, QHeaderView
from lib.ui.ui_assets import tool_button
from lib.core.binary_alignment import align_binary
from lib.core.core import pair_stamp


def difference_ranges(left, right):
    return align_binary(left, right).blocks


def load_binary_pair(pair):
    result = []
    for path in map(Path, pair):
        if path.is_symlink() or path.is_junction(): raise ValueError('不支援連結。')
        if not path.exists(): result.append(None); continue
        before = path.stat()
        data = path.read_bytes()
        after = path.stat()
        if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
            raise OSError(f'讀取期間檔案已變更：{path}')
        result.append(data)
    return result


def load_binary_comparison(pair):
    before = pair_stamp(*pair)
    documents = load_binary_pair(pair)
    alignment = align_binary(*(data or b'' for data in documents))
    if pair_stamp(*pair) != before: raise OSError('檔案在比較期間變更，請重新比較。')
    return documents, alignment, before


class HexOverview(QWidget):
    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.setFixedWidth(22)
        self.setToolTip('紅色為差異位置；按一下可跳到對應範圍')

    def intervals(self):
        total = max(1, self.owner.alignment.length)
        # 壓縮到畫素列並合併重疊，不隨檔案位元組數增加繪圖次數。
        result = []
        for start, end in self.owner.blocks:
            top = int(start / total * self.height())
            bottom = min(self.height(), max(top + 1, int((end + 15) / total * self.height())))
            if result and top <= result[-1][1]: result[-1] = (result[-1][0], max(bottom, result[-1][1]))
            else: result.append((top, bottom))
        return result

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor('#f4f4f4'))
        for top, bottom in self.intervals():
            painter.fillRect(3, top, self.width() - 6, bottom - top, QColor('#ed8585'))
        view = self.owner.views[0]
        total = max(1, self.owner.models[0].rowCount())
        first = max(0, view.rowAt(0))
        count = max(1, view.viewport().height() // max(1, view.verticalHeader().defaultSectionSize()))
        painter.setPen(QColor('#587ba5'))
        painter.drawRect(QRect(1, int(first / total * self.height()), self.width() - 3,
                               max(3, int(min(count, total) / total * self.height()) - 1)))

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton: return
        row = int(event.position().y() / max(1, self.height()) * self.owner.models[0].rowCount())
        self.owner.jump_to(min(max(0, row * 16), max(0, self.owner.alignment.length - 1)))


class HexModel(QAbstractTableModel):
    def __init__(self, owner, side):
        super().__init__(owner); self.owner = owner; self.side = side

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else (self.owner.alignment.length + 15) // 16

    def columnCount(self, parent=QModelIndex()): return 0 if parent.isValid() else 18

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return '位址' if section == 0 else '字元' if section == 17 else f'{section - 1:02X}'

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid(): return None
        data = self.owner.documents[self.side] or b''
        offset = index.row() * 16
        column = index.column()
        positions = [self.owner.raw_offset(self.side, position) for position in range(offset, min(offset + 16, self.owner.alignment.length))]
        if role == Qt.DisplayRole:
            if column == 0:
                first = next((position for position in positions if position is not None), None)
                return f'{first:08X}' if first is not None else ''
            if column == 17:
                return ''.join(' ' if position is None else chr(data[position]) if 32 <= data[position] < 127 else '.' for position in positions)
            position = self.owner.raw_offset(self.side, offset + column - 1)
            return f'{data[position]:02X}' if position is not None else ''
        if role == Qt.ToolTipRole and 1 <= column <= 16:
            position = self.owner.raw_offset(self.side, offset + column - 1)
            return f'原始位址：{position:08X}' if position is not None else '對側插入／本側缺少的位元組（顯示補位）'
        if role == Qt.TextAlignmentRole: return int(Qt.AlignCenter if column != 17 else Qt.AlignLeft | Qt.AlignVCenter)
        if role in (Qt.ForegroundRole, Qt.BackgroundRole):
            if column == 0: return QColor('#888888') if role == Qt.ForegroundRole else None
            slots = range(offset, offset + 16) if column == 17 else (offset + column - 1,)
            different = any(self.owner.is_difference(position) for position in slots)
            if different: return QColor('#d00000' if role == Qt.ForegroundRole else '#ffe4e4')
            if role == Qt.ForegroundRole: return QColor('#111111')


class HexCompare(QWidget):
    saved = Signal()
    compared = Signal()

    def __init__(self, left, right, parent=None, documents=None, alignment=None, stamp=None):
        super().__init__(parent)
        self.file_pair = (Path(left).resolve(), Path(right).resolve())
        if documents is None:
            documents, alignment, stamp = load_binary_comparison(self.file_pair)
        self.documents = list(documents)
        self.alignment = alignment if alignment is not None else align_binary(*(data or b'' for data in self.documents))
        self.stamp = stamp
        self.blocks = self.alignment.blocks
        self.starts = [start for start, _ in self.blocks]
        self.current = -1
        layout = QVBoxLayout(self); layout.setContentsMargins(2, 2, 2, 2); layout.setSpacing(2)
        toolbar = QHBoxLayout()
        for text, icon, direction in (('上一個差異', 'imgDiffSectionPrevNone', -1), ('下一個差異', 'imgDiffSectionNextNone', 1)):
            button = tool_button(self, text, icon); button.clicked.connect(lambda checked=False, d=direction: self.navigate(d))
            toolbar.addWidget(button)
        self.status = QLabel(); toolbar.addWidget(self.status); toolbar.addStretch(); layout.addLayout(toolbar)
        self.views = []; self.labels = []; self.models = []
        splitter = QSplitter(Qt.Horizontal); splitter.setHandleWidth(3)
        for side, path in enumerate(self.file_pair):
            pane = QWidget(); column = QVBoxLayout(pane); column.setContentsMargins(0, 0, 0, 0); column.setSpacing(2)
            label = QLabel(); label.setToolTip(str(path)); self.labels.append(label); column.addWidget(label)
            view = QTableView(); view.setObjectName('hexView'); view.setFont(QFont('Consolas', 10)); model = HexModel(self, side); view.setModel(model)
            view.setEditTriggers(QTableView.NoEditTriggers); view.setSelectionMode(QTableView.SingleSelection)
            view.verticalHeader().hide(); view.verticalHeader().setDefaultSectionSize(20)
            view.horizontalHeader().setSectionResizeMode(QHeaderView.Fixed)
            view.setColumnWidth(0, 76)
            for number in range(1, 17): view.setColumnWidth(number, 25)
            view.setColumnWidth(17, 145); view.setShowGrid(False)
            self.views.append(view); self.models.append(model); column.addWidget(view, 1); splitter.addWidget(pane)
        for side, view in enumerate(self.views):
            view.verticalScrollBar().valueChanged.connect(self.views[1 - side].verticalScrollBar().setValue)
            view.horizontalScrollBar().valueChanged.connect(self.views[1 - side].horizontalScrollBar().setValue)
        self.overview = HexOverview(self)
        body = QHBoxLayout(); body.setSpacing(2)
        body.addWidget(self.overview); body.addWidget(splitter, 1)
        layout.addLayout(body, 1)
        for view in self.views:
            view.verticalScrollBar().valueChanged.connect(lambda *_: self.overview.update())
        self.update_labels(); self.resize_columns()

    def resize_columns(self):
        for view in self.views:
            view.ensurePolished()
            metrics = QFontMetrics(view.font())
            view.setColumnWidth(0, metrics.horizontalAdvance('00000000') + 12)
            for column in range(1, 17): view.setColumnWidth(column, metrics.horizontalAdvance('00') + 8)
            view.setColumnWidth(17, metrics.horizontalAdvance('M' * 16) + 12)
            view.verticalHeader().setDefaultSectionSize(metrics.height() + 4)

    @property
    def dirty(self): return (False, False)

    @property
    def disk_baseline(self): return tuple(self.documents)

    def update_labels(self):
        for side, (path, data) in enumerate(zip(self.file_pair, self.documents)):
            self.labels[side].setText(f'{path.name} — {len(data):,} 位元組' if data is not None else f'{path.name} — 檔案不存在，無法操作')
            self.views[side].setEnabled(data is not None)
        self.status.setText(f'十六進位比較（唯讀）　{len(self.blocks)} 個差異區塊　內容對齊')

    def raw_offset(self, side, position):
        return self.alignment.raw_offset(side, position)

    def is_difference(self, offset):
        index = bisect_right(self.starts, offset) - 1
        return index >= 0 and offset < self.blocks[index][1]

    def navigate(self, direction):
        if not self.blocks: return
        self.current = (self.current + direction) % len(self.blocks) if self.current >= 0 else (0 if direction > 0 else len(self.blocks) - 1)
        offset = self.blocks[self.current][0]
        self.jump_to(offset)

    def jump_to(self, offset):
        if not self.alignment.length: return
        offset = max(0, min(offset, self.alignment.length - 1))
        for view, model in zip(self.views, self.models):
            index = model.index(offset // 16, offset % 16 + 1)
            view.setCurrentIndex(index); view.scrollTo(index, QTableView.PositionAtCenter)
        addresses = [self.raw_offset(side, offset) for side in (0, 1)]
        self.status.setText('唯讀　' + '　'.join(f'{label}：{value:08X}' if value is not None else f'{label}：補位' for label, value in zip(('左位址', '右位址'), addresses)))
        self.overview.update()

    def apply_disk_update(self, updated, baseline):
        if updated is None or baseline != self.disk_baseline: return
        documents, alignment, stamp = updated
        if tuple(documents) == self.disk_baseline:
            self.stamp = stamp
            self.compared.emit()
            return
        scroll = self.views[0].verticalScrollBar().value()
        for model in self.models: model.beginResetModel()
        self.documents = documents; self.alignment = alignment; self.stamp = stamp
        self.blocks = alignment.blocks; self.starts = [start for start, _ in self.blocks]; self.current = -1
        for model in self.models: model.endResetModel()
        self.update_labels(); self.views[0].verticalScrollBar().setValue(scroll)
        self.overview.update(); self.compared.emit()
