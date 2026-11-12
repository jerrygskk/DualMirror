"""文字差異檢視與區塊合併。"""
from pathlib import Path
import hashlib
import difflib
from PySide6.QtCore import Qt, Signal, QRect, QSize, QPoint, QTimer, QEvent
from PySide6.QtGui import QColor, QBrush, QRegion, QPainter, QTextCursor, QTextFormat, QKeySequence, QShortcut
from PySide6.QtWidgets import (QWidget, QPlainTextEdit, QTextEdit, QVBoxLayout,
                               QHBoxLayout, QLabel, QPushButton, QSplitter, QStyle, QLineEdit,
                               QApplication, QFileDialog, QMenu, QToolTip, QPlainTextDocumentLayout, QComboBox,
                               QRadioButton, QButtonGroup)
from lib.core.core import TextFile, differences, merge_block, fingerprint, atomic_write
from lib.ui.ui_common import confirmBox, msgCritical, msgInfo, icon_button
from lib.ui.syntax_styles import LANGUAGES, SyntaxHighlighter, detect_language
from lib.core.text_encoding import ENCODINGS, encoding_label
from lib.ui.ui_assets import app_icon, tool_button, separator


class AlignedDocumentLayout(QPlainTextDocumentLayout):
    def __init__(self, document, comparison):
        super().__init__(document)
        self.comparison = comparison

    def blockBoundingRect(self, block):
        rect = super().blockBoundingRect(block)
        if block.isVisible():
            margin = self.document().documentMargin() if not block.next().isValid() else 0
            rect.setHeight(max(rect.height() - margin, self.comparison.row_height) + margin)
        return rect


class NumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor
        self._drag_line = None

    def sizeHint(self):
        return QSize(self.editor.number_width(), 0)

    def paintEvent(self, event):
        self.editor.paint_numbers(event)

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton: return
        self.editor.comparison.flush_edit()
        line = self.editor.cursorForPosition(QPoint(0, int(event.position().y()))).blockNumber()
        if event.position().x() < 24 and any(start == line for start, end, custom in self.editor.merge_ranges()):
            self.editor.copy_at_line(line)
        else:
            self._drag_line = line
            self.editor.select_whole_rows(line, line)

    def mouseMoveEvent(self, event):
        if self._drag_line is not None:
            y = int(event.position().y())
            scroll = self.editor.verticalScrollBar()
            if y < 0: scroll.setValue(scroll.value() - scroll.singleStep())
            elif y >= self.height(): scroll.setValue(scroll.value() + scroll.singleStep())
            line = self.editor.cursorForPosition(QPoint(0, y)).blockNumber()
            self.editor.select_whole_rows(self._drag_line, line)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._drag_line is not None:
            self.mouseMoveEvent(event)
            self._drag_line = None

    def event(self, event):
        if event.type() == QEvent.ToolTip:
            line = self.editor.cursorForPosition(QPoint(0, event.pos().y())).blockNumber()
            if event.pos().x() < 24 and any(start == line for start, end, custom in self.editor.merge_ranges()):
                QToolTip.showText(event.globalPos(),
                    '複製區塊至右側' if self.editor.side == 0 else '複製區塊至左側', self)
            else:
                QToolTip.hideText()
            return True
        return super().event(event)


class Editor(QPlainTextEdit):
    def __init__(self, comparison, side):
        super().__init__()
        self.comparison, self.side = comparison, side
        self._aligned_layout = AlignedDocumentLayout(self.document(), comparison)
        self.document().setDocumentLayout(self._aligned_layout)
        self.line_numbers = []
        self.raw_positions = [0]
        self.setAcceptDrops(False)
        self.setUndoRedoEnabled(False)
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.numbers = NumberArea(self)
        self.blockCountChanged.connect(self.update_margin)
        self.updateRequest.connect(self.update_numbers)
        self.update_margin()

    def mousePressEvent(self, event):
        self.comparison.flush_edit()
        super().mousePressEvent(event)
        if event.button() == Qt.LeftButton: self.update_custom_rows()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.FontChange and hasattr(self, 'comparison') and hasattr(self.comparison, 'right_edit'):
            self.comparison.line_height_timer.start(0)

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        if event.buttons() & Qt.LeftButton: self.update_custom_rows()

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        if event.button() == Qt.LeftButton: self.update_custom_rows()

    def update_custom_rows(self):
        cursor = self.textCursor()
        first = self.document().findBlock(cursor.selectionStart()).blockNumber()
        last = self.document().findBlock(cursor.selectionEnd()).blockNumber()
        if cursor.hasSelection() and cursor.selectionEnd() == self.document().findBlockByNumber(last).position(): last -= 1
        self.comparison.custom_rows = (self.side, first, max(first + 1, last + 1))
        for editor in (self.comparison.left_edit, self.comparison.right_edit): editor.numbers.update()

    def select_whole_rows(self, anchor, line):
        first, last = sorted((anchor, line))
        cursor = QTextCursor(self.document().findBlockByNumber(first))
        end = self.document().findBlockByNumber(last + 1)
        cursor.setPosition(end.position() if end.isValid() else self.document().characterCount() - 1, QTextCursor.KeepAnchor)
        self.setFocus()
        self.setTextCursor(cursor)
        self.update_custom_rows()

    def merge_ranges(self):
        custom = self.comparison.custom_rows
        ranges = [(start, end, False) for start, end in self.comparison.display_blocks
                  if custom is None or custom[0] != self.side or end <= custom[1] or start >= custom[2]]
        if custom is not None and custom[0] == self.side:
            ranges.append((custom[1], custom[2], True))
        return ranges

    def insertFromMimeData(self, source):
        if source.hasText():
            self.comparison.replace_selection(self.side, source.text().replace('\r\n', '\n').replace('\r', '\n'))

    def copy(self):
        self.comparison.flush_edit()
        a, b = self.comparison.selection_offsets(self.side)
        if a != b:
            QApplication.clipboard().setText(self.comparison.texts[self.side][a:b])

    def cut(self):
        self.copy()
        self.comparison.replace_selection(self.side, '')

    def paste(self):
        self.insertFromMimeData(QApplication.clipboard().mimeData())

    def keyPressEvent(self, event):
        self.comparison.flush_edit()
        for key, action in ((QKeySequence.Copy, self.copy), (QKeySequence.Cut, self.cut),
                            (QKeySequence.Paste, self.paste), (QKeySequence.Undo, self.comparison.undo),
                            (QKeySequence.Redo, self.comparison.redo)):
            if event.matches(key):
                action(); event.accept(); return
        super().keyPressEvent(event)

    def inputMethodEvent(self, event):
        self.comparison.flush_edit()
        # An IME can report an entire paragraph as changed. Keep its actual
        # insertion point so repeated characters cannot move the caret.
        position = self.textCursor().selectionStart() + event.replacementStart()
        positions = self.raw_positions
        origin = positions[max(0, min(position, len(positions) - 1))]
        super().inputMethodEvent(event)
        if self.comparison._pending_edit is not None and (event.commitString() or event.replacementLength()):
            committed = event.commitString().replace('\r\n', '\n').replace('\r', '\n')
            self.comparison._pending_edit = (self.side, origin + len(committed))

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        for title, callback in (('復原', self.comparison.undo), ('取消復原', self.comparison.redo),
                                ('剪下', self.cut), ('複製', self.copy), ('貼上', self.paste),
                                ('全選', self.selectAll)):
            menu.addAction(title, callback)
        menu.exec(event.globalPos())

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self.comparison.active_side = self.side
        if hasattr(self.comparison, 'position_labels'):
            self.comparison.highlight()
            self.comparison.update_positions()

    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            delta = 1 if event.angleDelta().y() > 0 else -1
            for editor in (self.comparison.left_edit, self.comparison.right_edit):
                font = editor.font()
                font.setPointSize(max(7, min(24, font.pointSize() + delta)))
                editor.setFont(font)
                editor.update_margin()
            event.accept()
        else:
            super().wheelEvent(event)

    def number_width(self):
        return 31 + self.fontMetrics().horizontalAdvance('9') * len(str(max(1, self.blockCount())))

    def copy_at_line(self, line):
        self.comparison.flush_edit()
        custom = self.comparison.custom_rows
        if custom is not None and custom[0] == self.side and line == custom[1]:
            self.comparison.copy_block('right' if self.side == 0 else 'left', rows=custom[1:])
            return
        if not any(start == line for start, end, is_custom in self.merge_ranges()): return
        self.comparison.custom_rows = None
        cursor = self.textCursor()
        cursor.clearSelection()
        self.setTextCursor(cursor)
        for index, (start, end) in enumerate(self.comparison.display_blocks):
            if start <= line < end:
                self.comparison.current = index
                self.comparison.copy_block('right' if self.side == 0 else 'left')
                return

    def update_margin(self, *_):
        self.setViewportMargins(self.number_width(), 0, 0, 0)

    def update_numbers(self, rect, dy):
        if dy:
            self.numbers.scroll(0, dy)
        else:
            self.numbers.update(0, rect.y(), self.numbers.width(), rect.height())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        area = self.contentsRect()
        self.numbers.setGeometry(QRect(area.left(), area.top(), self.number_width(), area.height()))

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self.viewport())
        clip = QRegion(event.rect())
        if self.hasFocus() and not self.textCursor().hasSelection():
            clip = clip.subtracted(QRegion(self.cursorRect()))
        painter.setClipRegion(clip)
        for index, (start, end) in enumerate(self.comparison.display_blocks):
            first = None
            for row in range(start, end + 1):
                missing = row < end and row < len(self.line_numbers) and self.line_numbers[row] is None
                if missing and first is None: first = row
                if first is None or missing: continue
                block = self.document().findBlockByNumber(first)
                last = self.document().findBlockByNumber(row - 1)
                if block.isVisible() and last.isValid():
                    top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
                    bottom = round(self.blockBoundingGeometry(last).translated(self.contentOffset()).bottom())
                    rect = QRect(0, top, self.viewport().width(), bottom - top)
                    painter.fillRect(rect, QColor('#ffffff'))
                    if self.textCursor().hasSelection():
                        a, b = self.textCursor().selectionStart(), self.textCursor().selectionEnd()
                        for selected in range(first, row):
                            item = self.document().findBlockByNumber(selected)
                            if a <= item.position() < b:
                                y = round(self.blockBoundingGeometry(item).translated(self.contentOffset()).top())
                                painter.fillRect(QRect(0, y, rect.width(), round(self.comparison.row_height)), self.palette().highlight())
                    painter.setBrushOrigin(0, top)
                    painter.fillRect(rect, QBrush(QColor('#c6c6c6'),
                        Qt.BDiagPattern if index == self.comparison.current else Qt.DiagCrossPattern))
                first = None

    def paint_numbers(self, event):
        painter = QPainter(self.numbers)
        painter.fillRect(event.rect(), QColor('#e4e4e4'))
        painter.setPen(QColor('#777777'))
        for start, end, custom in self.merge_ranges():
            if end - start <= 1: continue
            first = self.document().findBlockByNumber(start)
            last = self.document().findBlockByNumber(end - 1)
            if not first.isValid() or not last.isValid() or not first.isVisible(): continue
            first_rect = self.blockBoundingGeometry(first).translated(self.contentOffset())
            last_rect = self.blockBoundingGeometry(last).translated(self.contentOffset())
            top = round(first_rect.top()) + max(0, (round(first_rect.height()) - 16) // 2) + 18
            bottom = round(last_rect.bottom()) - 3
            if bottom < event.rect().top() or top > event.rect().bottom(): continue
            painter.drawLine(12, top, 12, bottom)
            painter.drawLine(12, bottom, 16, bottom)
        block = self.firstVisibleBlock()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        while block.isValid() and top <= event.rect().bottom():
            height = round(self.blockBoundingRect(block).height())
            if block.isVisible() and top + height >= event.rect().top():
                line = block.blockNumber()
                arrows = [(start, custom) for start, end, custom in self.merge_ranges() if start == line]
                if arrows:
                    prefix = 'imgGutterCopyCustom' if arrows[0][1] else 'imgGutterCopySection'
                    icon = app_icon(prefix + ('Right' if self.side == 0 else 'Left'))
                    icon.paint(painter, 4, top + max(0, (height - 16) // 2), 16, 16)
                painter.setPen(QColor('#777777'))
                painter.drawText(0, top, self.number_width() - 7, self.fontMetrics().height(),
                                 Qt.AlignRight, str(self.line_numbers[block.blockNumber()] or '') if block.blockNumber() < len(self.line_numbers) else '')
            top += height
            block = block.next()


class Overview(QWidget):
    def __init__(self, comparison):
        super().__init__(comparison)
        self.comparison = comparison
        self.setFixedWidth(14)
        self.setToolTip('差異總覽；按一下可跳到附近的差異區塊')

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor('#ececee'))
        total = max(1, self.comparison.left_edit.blockCount())
        for index, (start, end) in enumerate(self.comparison.display_blocks):
            painter.fillRect(2, int(start / total * self.height()), 10,
                             max(3, int((end - start) / total * self.height())),
                             QColor('#318bce' if index == self.comparison.current else '#e36d61'))

    def mousePressEvent(self, event):
        if not self.comparison.display_blocks: return
        line = event.position().y() / max(1, self.height()) * self.comparison.left_edit.blockCount()
        self.comparison.current = min(range(len(self.comparison.display_blocks)), key=lambda i: abs(self.comparison.display_blocks[i][0] - line))
        self.comparison.refresh(); self.comparison.jump()


class TextCompare(QWidget):
    saved = Signal()
    path_requested = Signal(int, str)

    def __init__(self, left, right, parent=None, documents=None, initial_blocks=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.file_paths = [Path(left), Path(right)]
        self.docs = documents if documents is not None else [TextFile.load(path) if path.exists() else None for path in self.file_paths]
        if not any(self.docs) or any(doc is None and path.exists() for doc, path in zip(self.docs, self.file_paths)):
            raise ValueError('此檔案不是可辨識的文字檔，請使用整份覆寫。')
        self.texts = [doc.text if doc is not None else '' for doc in self.docs]
        self._initial_blocks = initial_blocks
        self.setWindowTitle(f'文字比較 — {Path(left).name} ↔ {Path(right).name}')
        self.resize(1450, 850)
        self.current = 0
        self.row_height = 0
        self.line_height_timer = QTimer(self)
        self.line_height_timer.setSingleShot(True)
        self.line_height_timer.timeout.connect(self.sync_line_height)
        self.blocks = []
        self.display_blocks = []
        self._scrolling = False
        self.filter_mode = 0
        self.active_side = 0 if self.docs[0] is not None else 1
        self.undo_stack, self.redo_stack = [], []
        self._rendering = False
        self._pending_edit = None
        self.custom_rows = None
        self.edit_timer = QTimer(self)
        self.edit_timer.setSingleShot(True)
        self.edit_timer.timeout.connect(self.flush_edit)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(2)
        bar = QHBoxLayout()
        bar.setSpacing(2)
        self.filter_buttons = []
        for index, (title, icon) in enumerate((('全部', 'imgFavAll'), ('差異', 'imgFavDiff'), ('相同', 'imgFavSame'))):
            button = tool_button(self, title, icon, True)
            button.clicked.connect(lambda checked=False, i=index: self.set_filter(i))
            self.filter_buttons.append(button)
            bar.addWidget(button)
        separator(bar)
        self.undo_button = tool_button(self, '復原（Ctrl+Z）', 'imgUndo')
        self.redo_button = tool_button(self, '取消復原（Ctrl+Y）', 'imgRedo')
        bar.addWidget(self.undo_button); bar.addWidget(self.redo_button)
        self.undo_button.clicked.connect(self.undo)
        self.redo_button.clicked.connect(self.redo)
        separator(bar)
        self.previous = icon_button(self, '上一處差異（Shift+F7）', QStyle.SP_ArrowUp)
        self.next = icon_button(self, '下一處差異（F7）', QStyle.SP_ArrowDown)
        self.to_left = icon_button(self, '複製到左側（有選取時複製右側選取行，否則複製差異區塊）', QStyle.SP_ArrowBack)
        self.to_right = icon_button(self, '複製到右側（有選取時複製左側選取行，否則複製差異區塊）', QStyle.SP_ArrowForward)
        self.save_left = icon_button(self, '儲存左側檔案', QStyle.SP_DialogSaveButton)
        self.save_right = icon_button(self, '儲存右側檔案', QStyle.SP_DialogSaveButton)
        for button in (self.to_left, self.to_right, self.next, self.previous):
            bar.addWidget(button)
        self.find_button = tool_button(self, '搜尋（Ctrl+F）', 'imgFind')
        self.find_button.clicked.connect(self.show_find)
        bar.addWidget(self.find_button)
        self.find_box = QLineEdit()
        self.find_box.setPlaceholderText('搜尋文字（Enter 下一處）')
        self.find_box.setMaximumWidth(220)
        self.find_box.hide()
        self.find_box.returnPressed.connect(self.find_next)
        bar.addWidget(self.find_box)
        self.search_scope = QWidget(self)
        self.search_scope.setAccessibleName('搜尋與取代範圍')
        scope_row = QHBoxLayout(self.search_scope)
        scope_row.setContentsMargins(0, 0, 0, 0)
        self.search_scope_group = QButtonGroup(self)
        self.search_scope_buttons = {}
        for title, value in (('雙側', 'both'), ('左側', 'left'), ('右側', 'right')):
            button = QRadioButton(title, self.search_scope)
            self.search_scope_group.addButton(button)
            self.search_scope_buttons[value] = button
            scope_row.addWidget(button)
        self.search_scope_buttons['both'].setChecked(True)
        self.search_scope.hide()
        bar.addWidget(self.search_scope)
        self.replace_button = tool_button(self, '搜尋與取代（Ctrl+H）', 'imgFind')
        self.replace_button.clicked.connect(self.show_replace)
        bar.addWidget(self.replace_button)
        self.close_find_button = QPushButton('× 關閉', self)
        self.close_find_button.setToolTip('關閉搜尋與取代（Esc）')
        self.close_find_button.clicked.connect(self.hide_find)
        self.close_find_button.hide()
        bar.addWidget(self.close_find_button)
        self.close_find_shortcut = QShortcut(QKeySequence('Escape'), self)
        self.close_find_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        self.close_find_shortcut.activated.connect(self.hide_find)
        self.close_find_shortcut.setEnabled(False)
        bar.addStretch()
        layout.addLayout(bar)
        self.replace_panel = QWidget(self)
        replace_row = QHBoxLayout(self.replace_panel)
        replace_row.setContentsMargins(0, 0, 0, 0)
        self.replace_box = QLineEdit()
        self.replace_box.setPlaceholderText('取代為（依搜尋範圍）')
        replace_row.addWidget(self.replace_box, 1)
        for title, all_matches in (('取代目前', False), ('全部取代', True)):
            button = QPushButton(title)
            button.clicked.connect(lambda checked=False, all_=all_matches: self.replace_matches(all_))
            replace_row.addWidget(button)
        self.replace_panel.hide()
        layout.addWidget(self.replace_panel)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        bar.addWidget(self.summary)
        splitter = QSplitter(Qt.Horizontal)
        self.left_edit, self.right_edit = Editor(self, 0), Editor(self, 1)
        self.labels = []
        self.language_boxes, self.encoding_boxes, self.syntax_highlighters = [], [], []
        self.encoding_overrides = [None, None]
        self.detected_encoding_labels = [encoding_label(doc) if doc is not None else '' for doc in self.docs]
        self.position_labels = []
        self.path_edits = []
        for side, (doc, editor) in enumerate(zip(self.docs, (self.left_edit, self.right_edit))):
            pane = QWidget(); pane_layout = QVBoxLayout(pane)
            pane_layout.setContentsMargins(0, 0, 0, 0)
            pane_layout.setSpacing(2)
            path_row = QHBoxLayout()
            path_row.setSpacing(3)
            path = QLineEdit(str(self.file_paths[side]))
            path.setAccessibleName(('左側' if side == 0 else '右側') + '檔案路徑')
            path.returnPressed.connect(lambda s=side: self.request_path(s))
            self.path_edits.append(path)
            path.setToolTip(str(self.file_paths[side]))
            browse = icon_button(self, ('左側' if side == 0 else '右側') + '：選擇檔案', QStyle.SP_FileIcon)
            browse.clicked.connect(lambda checked=False, s=side: self.browse_path(s))
            path_row.addWidget(browse)
            path_row.addWidget(path, 1)
            path_row.addWidget(self.save_left if side == 0 else self.save_right)
            pane_layout.addLayout(path_row)
            label = QLabel()
            label.setTextFormat(Qt.PlainText)
            metadata = QHBoxLayout()
            metadata.setContentsMargins(0, 0, 0, 0)
            metadata.setSpacing(8)
            metadata.addWidget(label)
            language = QComboBox()
            language.setAccessibleName(('左側' if side == 0 else '右側') + '語言樣式')
            language.addItem('自動偵測', '')
            for alias, title, extensions in LANGUAGES: language.addItem(title, alias)
            language.currentIndexChanged.connect(lambda _, s=side: self.change_language(s))
            metadata.addWidget(language)
            encoding = QComboBox()
            encoding.setAccessibleName(('左側' if side == 0 else '右側') + '文字編碼')
            encoding.addItem('自動偵測', None)
            for title, codec in ENCODINGS: encoding.addItem(title, codec)
            encoding.currentIndexChanged.connect(lambda _, s=side: self.change_encoding(s))
            metadata.addWidget(encoding)
            metadata.addStretch()
            pane_layout.addLayout(metadata)
            self.language_boxes.append(language)
            self.encoding_boxes.append(encoding)
            self.syntax_highlighters.append(SyntaxHighlighter(editor))
            self.labels.append(label)
            pane_layout.addWidget(editor)
            position = QLabel()
            position.setMinimumHeight(18)
            self.position_labels.append(position)
            pane_layout.addWidget(position)
            editor.setPlainText(self.texts[side])
            editor.setReadOnly(False)
            editor.document().contentsChange.connect(lambda p, r, a, s=side: self.editor_changed(s, p, r, a))
            splitter.addWidget(pane)
        body = QHBoxLayout()
        body.setSpacing(3)
        self.overview = Overview(self)
        body.addWidget(self.overview)
        body.addWidget(splitter, 1)
        layout.addLayout(body, 1)
        self.previous.clicked.connect(lambda: self.navigate(-1))
        self.next.clicked.connect(lambda: self.navigate(1))
        self.to_left.clicked.connect(lambda: self.copy_block('left'))
        self.to_right.clicked.connect(lambda: self.copy_block('right'))
        self.save_left.clicked.connect(lambda: self.save_side(0))
        self.save_right.clicked.connect(lambda: self.save_side(1))
        self.left_edit.cursorPositionChanged.connect(lambda: self.select_cursor(0))
        self.right_edit.cursorPositionChanged.connect(lambda: self.select_cursor(1))
        for source, target in ((self.left_edit, self.right_edit), (self.right_edit, self.left_edit)):
            source.verticalScrollBar().valueChanged.connect(lambda value, dest=target: self.sync_scroll(dest, value))
            source.horizontalScrollBar().valueChanged.connect(target.horizontalScrollBar().setValue)
        QShortcut(QKeySequence('F7'), self, activated=lambda: self.navigate(1))
        QShortcut(QKeySequence('Shift+F7'), self, activated=lambda: self.navigate(-1))
        QShortcut(QKeySequence('F3'), self, activated=self.find_next)
        QShortcut(QKeySequence('Shift+F3'), self, activated=lambda: self.find_next(True))
        self.refresh()
        self.jump()
        (self.left_edit if self.docs[0] is not None else self.right_edit).setFocus()

    def request_path(self, side):
        value = self.path_edits[side].text().strip().strip('"')
        self.path_requested.emit(side, value)
        self.path_edits[side].setText(str(self.file_paths[side]))

    def browse_path(self, side):
        name, _ = QFileDialog.getOpenFileName(self, '選擇比較檔案', str(self.file_paths[side]), '所有檔案 (*)')
        if name:
            self.path_requested.emit(side, name)

    @staticmethod
    def newline_name(newline):
        return {'\r\n': 'CRLF', '\n': 'LF', '\r': 'CR'}[newline]

    @property
    def dirty(self):
        return [doc is not None and text != doc.text for text, doc in zip(self.texts, self.docs)]

    @property
    def disk_baseline(self):
        return tuple(doc.original if doc is not None else None for doc in self.docs)

    def refresh(self):
        self.custom_rows = None
        self._rendering = True
        self.blocks = self._initial_blocks if self._initial_blocks is not None else differences(*self.texts)
        self._initial_blocks = None
        self.align_display()
        self.current = min(self.current, max(0, len(self.blocks) - 1))
        self.save_left.setEnabled(self.dirty[0])
        self.save_right.setEnabled(self.dirty[1])
        self.undo_button.setEnabled(bool(self.undo_stack))
        self.redo_button.setEnabled(bool(self.redo_stack))
        for button in (self.previous, self.next):
            button.setEnabled(bool(self.blocks))
        for button in (self.to_left, self.to_right):
            button.setEnabled(bool(self.blocks) and all(doc is not None for doc in self.docs))
        for editor, doc in zip((self.left_edit, self.right_edit), self.docs):
            editor.setEnabled(doc is not None)
            editor.setPlaceholderText('檔案不存在，無法操作' if doc is None else '')
        self.summary.setText(f'差異 {self.current + 1 if self.blocks else 0}／{len(self.blocks)}' + ('　● 未儲存' if any(self.dirty) else ''))
        self.highlight()
        self.apply_filter()
        self.overview.update()
        self.update_positions()
        for label, doc in zip(self.labels, self.docs):
            label.setText('檔案不存在，無法操作' if doc is None else f'{len(doc.original):,} 位元組　{self.newline_name(doc.newline)}')
        self.update_formats()
        self._rendering = False

    def update_formats(self):
        for side, doc in enumerate(self.docs):
            language, encoding = self.language_boxes[side], self.encoding_boxes[side]
            language.setEnabled(doc is not None)
            encoding.setEnabled(doc is not None)
            if doc is None: continue
            detected = detect_language(self.file_paths[side], self.texts[side])
            title = next(title for alias, title, _ in LANGUAGES if alias == detected)
            language.setItemText(0, f'自動偵測（{title}）')
            self.syntax_highlighters[side].set_source(self.texts[side], language.currentData() or detected)
            encoding.setItemText(0, f'自動偵測（{self.detected_encoding_labels[side]}）')

    def change_language(self, side):
        self.flush_edit()
        self._rendering = True
        try: self.update_formats()
        finally: self._rendering = False

    def change_encoding(self, side):
        self.flush_edit()
        box = self.encoding_boxes[side]
        chosen = box.currentData()
        try:
            if self.docs[side] is None: return
            if any(self.dirty):
                msgInfo('尚有未儲存變更', '請先儲存或復原變更，再切換文字編碼。', self)
                return
            self.check_files()
            doc = TextFile.from_bytes(self.file_paths[side], self.docs[side].original, chosen)
            if doc is None: raise UnicodeError('此編碼無法將檔案解讀為文字。')
            self.docs[side], self.texts[side] = doc, doc.text
            self.encoding_overrides[side] = chosen
            if chosen is None: self.detected_encoding_labels[side] = encoding_label(doc)
            self.undo_stack.clear(); self.redo_stack.clear()
            self.refresh()
        except (UnicodeError, LookupError, OSError, RuntimeError) as error:
            msgCritical('無法切換文字編碼', str(error), self)
        finally:
            box.blockSignals(True)
            box.setCurrentIndex(box.findData(self.encoding_overrides[side]))
            box.blockSignals(False)

    def selection_offsets(self, side):
        editor = (self.left_edit, self.right_edit)[side]
        cursor = editor.textCursor()
        positions = editor.raw_positions
        return tuple(positions[min(p, len(positions) - 1)] for p in (cursor.selectionStart(), cursor.selectionEnd()))

    def commit_text(self, side, text, caret=None):
        if self.docs[side] is None or text == self.texts[side]: return
        self.undo_stack.append(tuple(self.texts))
        self.redo_stack.clear()
        self.texts[side] = text
        self.refresh()
        if caret is not None: self.place_cursor(side, caret)

    def place_cursor(self, side, offset, anchor=None):
        editor = (self.left_edit, self.right_edit)[side]
        positions = editor.raw_positions
        def location(value):
            return next((i for i, raw in enumerate(positions) if raw >= value), len(positions) - 1)
        cursor = editor.textCursor()
        cursor.setPosition(location(offset if anchor is None else anchor))
        if anchor is not None: cursor.setPosition(location(offset), QTextCursor.KeepAnchor)
        editor.setTextCursor(cursor)

    def replace_selection(self, side, inserted):
        self.flush_edit()
        if self.docs[side] is None: return
        a, b = self.selection_offsets(side)
        text = self.texts[side]
        editor = (self.left_edit, self.right_edit)[side]
        row = editor.document().findBlock(editor.textCursor().selectionStart()).blockNumber()
        inserted, caret = self.prepare_insertion(side, row, a, b, inserted)
        self.commit_text(side, text[:a] + inserted + text[b:], caret)

    def prepare_insertion(self, side, row, a, b, inserted):
        editor = (self.left_edit, self.right_edit)[side]
        text = self.texts[side]
        caret = a + len(inserted)
        if inserted and a == b and row < len(editor.line_numbers) and editor.line_numbers[row] is None:
            prefix = '\n' if a and text[a - 1] != '\n' else ''
            suffix = '\n' if a < len(text) and not inserted.endswith('\n') else ''
            caret += len(prefix)
            inserted = prefix + inserted + suffix
        return inserted, caret

    def editor_changed(self, side, position, removed, added):
        if self._rendering or self.docs[side] is None: return
        editor = (self.left_edit, self.right_edit)[side]
        previous, current = editor.qt_snapshot, editor.toPlainText()
        if previous == current: return
        # IME formatting changes may report unchanged surrounding text as
        # removed/added, including display-only alignment rows. Map only the
        # actual textual difference back to the original document.
        old_segment = previous.encode('utf-16-le')[position * 2:(position + removed) * 2].decode('utf-16-le')
        new_segment = current.encode('utf-16-le')[position * 2:(position + added) * 2].decode('utf-16-le')
        first = 0
        while first < min(len(old_segment), len(new_segment)) and old_segment[first] == new_segment[first]: first += 1
        old_end, new_end = len(old_segment), len(new_segment)
        while old_end > first and new_end > first and old_segment[old_end - 1] == new_segment[new_end - 1]:
            old_end -= 1
            new_end -= 1
        position += len(old_segment[:first].encode('utf-16-le')) // 2
        removed = len(old_segment[first:old_end].encode('utf-16-le')) // 2
        added = len(new_segment[first:new_end].encode('utf-16-le')) // 2
        positions = editor.raw_positions
        a = positions[min(position, len(positions) - 1)]
        b = positions[min(position + removed, len(positions) - 1)]
        cursor = QTextCursor(editor.document())
        cursor.setPosition(position)
        cursor.setPosition(min(position + added, editor.document().characterCount() - 1), QTextCursor.KeepAnchor)
        inserted = cursor.selectedText().replace('\u2029', '\n')
        row = editor.display_snapshot.encode('utf-16-le')[:position * 2].decode('utf-16-le', errors='ignore').count('\n')
        inserted, caret = self.prepare_insertion(side, row, a, b, inserted)
        old = self.texts[side]
        text = old[:a] + inserted + old[b:]
        if text != old:
            self.undo_stack.append(tuple(self.texts)); self.redo_stack.clear()
            self.texts[side] = text
        # 下一個輸入事件前刷新對齊；Qt 尚在修改 document 時不重建它。
        self._pending_edit = (side, caret)
        self.edit_timer.start(0)

    def flush_edit(self):
        if self._pending_edit is None: return
        side, caret = self._pending_edit
        self._pending_edit = None
        self.edit_timer.stop()
        self.refresh()
        self.place_cursor(side, caret)

    def show_replace(self):
        self.show_find()
        self.replace_panel.show()

    def replace_matches(self, all_matches=False):
        self.flush_edit()
        query = self.find_box.text()
        if not query: return
        sides = self.search_sides()
        replacement = self.replace_box.text()
        if all_matches:
            count = sum(self.texts[side].count(query) for side in sides)
            updated = list(self.texts)
            for side in sides: updated[side] = updated[side].replace(query, replacement)
            if updated != self.texts:
                self.undo_stack.append(tuple(self.texts))
                self.redo_stack.clear()
                self.texts = updated
                self.refresh()
            self.summary.setText(f'已取代 {count} 處（{self.search_scope_group.checkedButton().text()}）')
        else:
            side = self.active_side
            a, b = self.selection_offsets(side)
            if side not in sides or self.texts[side][a:b] != query:
                self.find_next()
                side = self.active_side
                a, b = self.selection_offsets(side)
            text = self.texts[side]
            if side in sides and text[a:b] == query:
                self.commit_text(side, text[:a] + replacement + text[b:], a + len(replacement))
                self.find_next()

    def apply_disk_update(self, documents, baseline):
        if any(self.dirty) or self.disk_baseline != baseline: return
        if documents is None or any(doc is None and path.exists() for doc, path in zip(documents, self.file_paths)):
            self.summary.setText('磁碟檔案格式變更或無法讀取，請重新開啟比較')
            return
        if self.disk_baseline == tuple(doc.original if doc is not None else None for doc in documents): return
        try:
            detected_labels = [encoding_label(doc) if doc is not None else '' for doc in documents]
            documents = [TextFile.from_bytes(path, doc.original, codec) if doc is not None and codec else doc
                         for path, doc, codec in zip(self.file_paths, documents, self.encoding_overrides)]
            if any(doc is None and path.exists() for doc, path in zip(documents, self.file_paths)):
                raise UnicodeError('外部變更無法使用指定編碼讀取。')
        except UnicodeError as error:
            self.summary.setText(str(error))
            return
        self.docs = documents
        self.detected_encoding_labels = detected_labels
        self.texts = [doc.text if doc is not None else '' for doc in documents]
        self.undo_stack.clear(); self.redo_stack.clear()
        self.refresh()

    def update_positions(self):
        for side, editor in enumerate((self.left_edit, self.right_edit)):
            cursor = editor.textCursor()
            row = cursor.blockNumber()
            number = editor.line_numbers[row] if row < len(editor.line_numbers) else None
            text = self.texts[side]
            selected = abs(cursor.position() - cursor.anchor())
            self.position_labels[side].setText(f'行：{number or "—"}　欄：{cursor.positionInBlock() + 1}　選取：{selected}　長度：{len(text):,}　行數：{len(text.splitlines())}')

    def show_find(self):
        self.find_box.show()
        self.search_scope.show()
        self.close_find_button.show()
        self.close_find_shortcut.setEnabled(True)
        self.find_box.setFocus()
        self.find_box.selectAll()

    def hide_find(self):
        self.find_box.hide()
        self.search_scope.hide()
        self.replace_panel.hide()
        self.close_find_button.hide()
        self.close_find_shortcut.setEnabled(False)
        (self.left_edit, self.right_edit)[self.active_side].setFocus()

    def search_sides(self):
        scope = next(key for key, button in self.search_scope_buttons.items() if button.isChecked())
        sides = {'both': (0, 1), 'left': (0,), 'right': (1,)}[scope]
        return tuple(side for side in sides if self.docs[side] is not None)

    def find_next(self, reverse=False):
        self.flush_edit()
        query = self.find_box.text()
        if not query: return
        sides = self.search_sides()
        if not sides: return
        from PySide6.QtGui import QTextDocument
        flags = QTextDocument.FindBackward if reverse else QTextDocument.FindFlags()
        start = self.active_side if self.active_side in sides else sides[-1 if reverse else 0]
        ordered = list(sides)
        if reverse: ordered.reverse()
        index = ordered.index(start)
        ordered = ordered[index:] + ordered[:index]
        for step, side in enumerate(ordered + [start]):
            editor = (self.left_edit, self.right_edit)[side]
            cursor = editor.textCursor()
            if step or self.active_side not in sides:
                cursor.movePosition(QTextCursor.End if reverse else QTextCursor.Start)
            found = editor.document().find(query, cursor, flags)
            if not found.isNull():
                editor.setTextCursor(found)
                editor.ensureCursorVisible()
                self.active_side = side
                self.summary.setText(f'搜尋結果：{"左側" if side == 0 else "右側"}')
                self.update_positions()
                return
        self.summary.setText('找不到符合的文字')
        self.update_positions()

    def undo(self):
        self.flush_edit()
        if not self.undo_stack: return
        self.redo_stack.append(tuple(self.texts))
        self.texts = list(self.undo_stack.pop())
        self.refresh(); self.jump()

    def redo(self):
        self.flush_edit()
        if not self.redo_stack: return
        self.undo_stack.append(tuple(self.texts))
        self.texts = list(self.redo_stack.pop())
        self.refresh(); self.jump()

    def set_filter(self, mode):
        self.flush_edit()
        self.filter_mode = mode
        self.apply_filter()

    def apply_filter(self):
        for index, button in enumerate(self.filter_buttons): button.setChecked(index == self.filter_mode)
        changed = {line for start, end in self.display_blocks for line in range(start, end)}
        for editor in (self.left_edit, self.right_edit):
            block = editor.document().firstBlock()
            while block.isValid():
                visible = self.filter_mode == 0 or ((block.blockNumber() in changed) == (self.filter_mode == 1))
                block.setVisible(visible)
                block.setLineCount(1 if visible else 0)
                block = block.next()
            editor.document().markContentsDirty(0, editor.document().characterCount())
            editor.viewport().update(); editor.numbers.update()

    def align_display(self):
        llines, rlines = [text.splitlines(True) for text in self.texts]
        displays, numbers, offsets = [[], []], [[], []], [[], []]
        line_offsets = [[0], [0]]
        for side, lines in enumerate((llines, rlines)):
            for raw in lines: line_offsets[side].append(line_offsets[side][-1] + len(raw))
        ranges = []
        def append_segment(a, b, c, d):
            count = max(b - a, d - c)
            for side, lines, start, end in ((0, llines, a, b), (1, rlines, c, d)):
                for offset in range(count):
                    exists = start + offset < end
                    raw = lines[start + offset] if exists else ''
                    displays[side].append(raw.removesuffix('\n').replace('\u2028', '↵').replace('\u2029', '¶'))
                    numbers[side].append(start + offset + 1 if exists else None)
                    offsets[side].append(line_offsets[side][min(start + offset, end)])
        pa = pc = 0
        for _, a, b, c, d in self.blocks:
            append_segment(pa, a, pc, c)
            start = len(displays[0])
            append_segment(a, b, c, d)
            ranges.append((start, len(displays[0])))
            pa, pc = b, d
        append_segment(pa, len(llines), pc, len(rlines))
        if any(text.endswith('\n') for text in self.texts):
            for side, text in enumerate(self.texts):
                displays[side].append('')
                numbers[side].append(len((llines, rlines)[side]) + 1 if text.endswith('\n') else None)
                offsets[side].append(len(text))
        self.display_blocks = ranges
        for side, editor in enumerate((self.left_edit, self.right_edit)):
            value = '\n'.join(displays[side])
            editor.display_snapshot = value
            # Qt 顯示字元可能正規化，資料始終只取 self.texts。
            editor.line_numbers = numbers[side]
            positions = []
            for row, displayed in enumerate(displays[side]):
                origin = offsets[side][row]
                for index, char in enumerate(displayed):
                    positions.extend([origin + index] * (len(char.encode('utf-16-le')) // 2))
                positions.append(origin + len(displayed))
                # 每列最後一個邊界同時是顯示換行前的位置。
            editor.raw_positions = positions or [0]
            if editor.toPlainText() != value:
                scroll = editor.verticalScrollBar().value()
                editor.blockSignals(True)
                editor.setPlainText(value)
                editor.verticalScrollBar().setValue(scroll)
                editor.blockSignals(False)
            editor.qt_snapshot = editor.toPlainText()
            editor.numbers.update()
        self.sync_line_height()

    def sync_line_height(self):
        editors = (self.left_edit, self.right_edit)
        height = max(editor.fontMetrics().height() for editor in editors)
        for editor in editors:
            layout = editor.document().documentLayout()
            block = editor.document().firstBlock()
            while block.isValid():
                natural = QPlainTextDocumentLayout.blockBoundingRect(layout, block).height()
                if not block.next().isValid(): natural -= editor.document().documentMargin()
                height = max(height, natural)
                block = block.next()
        if height == self.row_height: return
        self.row_height = height
        scrolling = self._scrolling
        self._scrolling = True
        for editor in editors:
            layout = editor.document().documentLayout()
            layout.documentSizeChanged.emit(layout.documentSize())
            layout.requestUpdate()
            editor.numbers.update()
        self.right_edit.verticalScrollBar().setValue(self.left_edit.verticalScrollBar().value())
        self._scrolling = scrolling

    def highlight(self):
        for side, editor in enumerate((self.left_edit, self.right_edit)):
            selections = []
            if side == self.active_side:
                current_line = QTextEdit.ExtraSelection()
                current_line.cursor = QTextCursor(editor.textCursor().block())
                current_line.format.setProperty(QTextFormat.FullWidthSelection, True)
                current_line.format.setBackground(QColor('#e8e8ff'))
                selections.append(current_line)
            for index, (tag, a, b, c, d) in enumerate(self.blocks):
                start, end = self.display_blocks[index]
                for line in range(start, max(start + 1, end)):
                    block = editor.document().findBlockByNumber(line)
                    if not block.isValid():
                        block = editor.document().lastBlock()
                    selection = QTextEdit.ExtraSelection()
                    selection.cursor = QTextCursor(block)
                    selection.format.setProperty(QTextFormat.FullWidthSelection, True)
                    placeholder = line >= len(editor.line_numbers) or editor.line_numbers[line] is None
                    if placeholder:
                        hatch = QBrush(QColor('#c6c6c6'),
                            Qt.BDiagPattern if index == self.current else Qt.DiagCrossPattern)
                        selection.format.setBackground(hatch)
                    else:
                        selection.format.setBackground(QColor('#ffe3e3' if block.text() else '#efefff'))
                        selection.format.setForeground(QColor('#ff0000'))
                    selections.append(selection)
                    if tag == 'replace' and not placeholder:
                        offset = line - start
                        llines, rlines = self.texts[0].splitlines(True), self.texts[1].splitlines(True)
                        lt = llines[a + offset].removesuffix('\n') if a + offset < b else ''
                        rt = rlines[c + offset].removesuffix('\n') if c + offset < d else ''
                        for kind, x, y, z, w in difflib.SequenceMatcher(None, lt, rt, autojunk=False).get_opcodes():
                            if kind == 'equal': continue
                            p, q, raw = (x, y, lt) if side == 0 else (z, w, rt)
                            if p == q: continue
                            accent = QTextEdit.ExtraSelection()
                            accent.cursor = QTextCursor(block)
                            origin = block.position()
                            accent.cursor.setPosition(origin + len(raw[:p].encode('utf-16-le')) // 2)
                            accent.cursor.setPosition(origin + len(raw[:q].encode('utf-16-le')) // 2, QTextCursor.KeepAnchor)
                            accent.format.setForeground(QColor('#e00000'))
                            accent.format.setBackground(QColor('#ffb9bc'))
                            selections.append(accent)
            editor.setExtraSelections(selections)

    def select_cursor(self, side):
        editor = (self.left_edit, self.right_edit)[side]
        line = editor.textCursor().blockNumber()
        for index, (start, end) in enumerate(self.display_blocks):
            if start <= line < max(start + 1, end):
                self.current = index
                self.summary.setText(f'差異 {self.current + 1}／{len(self.blocks)}' + ('　● 未儲存' if any(self.dirty) else ''))
                break
        self.active_side = side
        self.highlight(); self.overview.update(); self.update_positions()

    def navigate(self, direction):
        self.flush_edit()
        if not self.blocks:
            return
        self.current = (self.current + direction) % len(self.blocks)
        self.refresh(); self.jump()

    def jump(self):
        if not self.blocks:
            return
        self._scrolling = True
        for editor in (self.left_edit, self.right_edit):
            line = self.display_blocks[self.current][0]
            block = editor.document().findBlockByNumber(line)
            if not block.isValid(): block = editor.document().lastBlock()
            editor.blockSignals(True)
            editor.setTextCursor(QTextCursor(block))
            editor.centerCursor()
            editor.blockSignals(False)
        self.right_edit.verticalScrollBar().setValue(self.left_edit.verticalScrollBar().value())
        self._scrolling = False

    def sync_scroll(self, target, value):
        if self._scrolling:
            return
        self._scrolling = True
        target.verticalScrollBar().setValue(value)
        self._scrolling = False

    def copy_block(self, destination, rows=None):
        self.flush_edit()
        if any(doc is None for doc in self.docs):
            return
        try:
            self.check_files()
        except Exception as error:
            msgCritical('無法複製區塊', str(error), self)
            return
        source, target = (0, 1) if destination == 'right' else (1, 0)
        source_editor = (self.left_edit, self.right_edit)[source]
        cursor = source_editor.textCursor()
        if rows is None and self.custom_rows is not None and self.custom_rows[0] == source:
            rows = self.custom_rows[1:]
        if rows is not None or cursor.hasSelection():
            if rows is not None:
                first, end = rows
                last = end - 1
            else:
                first = source_editor.document().findBlock(cursor.selectionStart()).blockNumber()
                last = source_editor.document().findBlock(cursor.selectionEnd()).blockNumber()
                if cursor.selectionEnd() == source_editor.document().findBlockByNumber(last).position(): last -= 1
            src_numbers = source_editor.line_numbers[first:last + 1]
            dst_editor = (self.left_edit, self.right_edit)[target]
            dst_numbers = dst_editor.line_numbers[first:last + 1]
            src_lines, dst_lines = self.texts[source].splitlines(True), self.texts[target].splitlines(True)
            selected = [n for n in src_numbers if n is not None and n <= len(src_lines)]
            existing = [n for n in dst_numbers if n is not None and n <= len(dst_lines)]
            if not selected and not existing: return
            if existing:
                a, b = existing[0] - 1, existing[-1]
            else:
                a = b = sum(n is not None and n <= len(dst_lines) for n in dst_editor.line_numbers[:first])
            dst_lines[a:b] = src_lines[selected[0] - 1:selected[-1]] if selected else []
            text = ''.join(dst_lines)
        else:
            if not self.blocks: return
            text = merge_block(*self.texts, self.blocks[self.current], destination)
        if text == self.texts[target]: return
        scroll = source_editor.verticalScrollBar().value()
        top_row = source_editor.firstVisibleBlock().blockNumber()
        anchor = next(((row, number) for row, number in enumerate(source_editor.line_numbers)
                       if row >= top_row and number is not None), None)
        horizontal = [editor.horizontalScrollBar().value() for editor in (self.left_edit, self.right_edit)]
        self.undo_stack.append(tuple(self.texts))
        self.redo_stack.clear()
        self.texts[1 if destination == 'right' else 0] = text
        self._scrolling = True
        try:
            self.refresh()
            if anchor is not None and anchor[1] in source_editor.line_numbers:
                scroll += source_editor.line_numbers.index(anchor[1]) - anchor[0]
            for editor, value in zip((self.left_edit, self.right_edit), horizontal):
                editor.verticalScrollBar().setValue(scroll)
                editor.horizontalScrollBar().setValue(value)
        finally:
            self._scrolling = False

    def check_files(self):
        for doc, path in zip(self.docs, self.file_paths):
            expected = hashlib.sha256(doc.original).digest() if doc is not None else None
            if fingerprint(path) != expected:
                raise RuntimeError(f'檔案已被其他程式修改，請關閉此視窗並重新比較：{path}')

    def save_side(self, side):
        self.flush_edit()
        if self.docs[side] is None or not self.dirty[side]:
            return
        try:
            self.check_files()
            self.docs[side].save(self.texts[side])
        except Exception as error:
            msgCritical('無法儲存', str(error), self)
            return
        self.refresh()
        self.saved.emit()

    def save_as(self, side, target=None):
        self.flush_edit()
        if self.docs[side] is None: return False
        if target is None:
            name, _ = QFileDialog.getSaveFileName(self, '另存新檔', str(self.file_paths[side]),
                                                 options=QFileDialog.DontConfirmOverwrite)
            if not name: return False
            target = Path(name)
        target = Path(target)
        try:
            if target.resolve() in [path.resolve() for path in self.file_paths]:
                raise ValueError('另存新檔請使用其他檔名；原檔請使用儲存。')
            expected = fingerprint(target)
            if expected is not None and not confirmBox('確認覆寫', f'覆寫此檔案？\n{target}',
                                                       confirm_text='覆寫', default_confirm=False, parent=self):
                return False
            self.check_files()
            raw = self.docs[side].encoded(self.texts[side])
            atomic_write(target, raw, expected)
        except Exception as error:
            msgCritical('無法另存新檔', str(error), self)
            return False
        self.saved.emit()
        self.summary.setText(f'已另存：{target}；原比較檔案未變更')
        return True

    def closeEvent(self, event):
        self.flush_edit()
        if any(self.dirty) and not confirmBox('未儲存變更', '捨棄未儲存的變更並關閉？', confirm_text='捨棄變更', default_confirm=False, parent=self):
            event.ignore()
        else:
            event.accept()
