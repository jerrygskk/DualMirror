"""雙欄檔案與資料夾比較工具。"""
from pathlib import Path
from datetime import datetime
from dataclasses import replace
import sys
from PySide6.QtCore import Qt, QThread, Signal, QFileSystemWatcher, QTimer
from PySide6.QtGui import QColor, QKeySequence, QShortcut, QAction, QIcon
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QLineEdit, QPushButton, QLabel, QFileDialog, QComboBox,
    QTreeWidget, QTreeWidgetItem, QHeaderView, QDialog, QDialogButtonBox,
    QPlainTextEdit, QStyle, QTabWidget, QTabBar, QSplitter, QAbstractItemView, QFrame, QMenu, QInputDialog, QStackedWidget)
from lib.core.core import compare_paths, TextFile, differences, sync_plan, execute_plan, make_action, selection_plan, roots, verify_contents, pair_stamp
from lib.ui.text_compare import TextCompare
from lib.ui.hex_compare import HexCompare, load_binary_comparison
from lib.ui.theme import APP_STYLE, apply_light_palette
from lib.ui.ui_common import msgCritical, msgInfo, icon_button, confirmBox
from lib.ui.ui_assets import app_icon, tool_button, separator, FolderSelectionDelegate
from lib.ui.comparison_gutter import ComparisonSplitter
from lib.ui.folder_presentation import FOLDER_DESCRIPTIONS, file_color, summarize_folders
from lib.settings.version import APP_NAME, __version__
from lib.paths import resource_path

STATUS = {'same': '相同', 'different': '內容不同', 'left': '僅左側存在', 'right': '僅右側存在', 'conflict': '檔案／資料夾衝突'}


class Worker(QThread):
    result = Signal(object)
    failed = Signal(str)

    def __init__(self, operation, parent):
        super().__init__(parent)
        self.operation = operation

    def run(self):
        try:
            self.result.emit(self.operation())
        except Exception as error:
            self.failed.emit(str(error))


class ComparisonSession(QMainWindow):
    def __init__(self, host=None):
        super().__init__(host)
        self.host = host
        self.setWindowTitle(f'{APP_NAME} v{__version__}')
        self.setWindowIcon(QIcon(str(resource_path('assets/DualMirror.ico'))))
        self.resize(1200, 700)
        self.busy = False
        self.rows = []
        self.workers = []
        self._file_requests = []
        self._loading_request = None
        self.windows = []
        self.compared_paths = None
        self.auto_open_files = False
        self.pending_documents = None
        self._refresh_pending = False
        self._confirmation_active = False
        self._closing = False
        self._content_epoch = 0
        self.watcher = QFileSystemWatcher(self)
        self.watcher.fileChanged.connect(self.invalidate_content)
        self.watcher.directoryChanged.connect(self.invalidate_content)
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setSingleShot(True)
        self.refresh_timer.setInterval(200)
        self.refresh_timer.timeout.connect(self.refresh_if_ready)
        self._syncing_tree = False
        self.active_tree_side = 0
        self.item_pairs = {}
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(False)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.workspace = QStackedWidget()
        self.workspace.addWidget(self.tabs)
        self.home = QWidget()
        home_layout = QVBoxLayout(self.home)
        home_layout.addStretch()
        label = QLabel('尚未開啟比較工作階段')
        label.setAlignment(Qt.AlignCenter)
        home_layout.addWidget(label)
        new_session = QPushButton('新增資料夾比較')
        new_session.clicked.connect(self.show_folder_tab)
        home_layout.addWidget(new_session, alignment=Qt.AlignHCenter)
        home_layout.addStretch()
        self.workspace.addWidget(self.home)
        self.setCentralWidget(self.workspace)
        widget = QWidget()
        self.folder_tab = widget
        self.tabs.addTab(widget, app_icon('imgDirCompareSession'), '資料夾比較')
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.setSpacing(2)
        path_panes = []
        self.left_path, self.right_path = QLineEdit(), QLineEdit()
        self.left_path.setPlaceholderText('檔案或資料夾路徑')
        self.right_path.setPlaceholderText('檔案或資料夾路徑')
        self.path_controls = []
        self.up_buttons = []
        for label, edit in (('左側', self.left_path), ('右側', self.right_path)):
            pane = QWidget(); column = QHBoxLayout(pane)
            column.setContentsMargins(0, 0, 0, 0)
            column.setSpacing(3)
            edit.setAccessibleName(f'{label}路徑')
            for caption, folder in (('選擇資料夾', True), ('選擇檔案', False)):
                button = icon_button(self, f'{label}：{caption}', QStyle.SP_DirOpenIcon if folder else QStyle.SP_FileIcon)
                button.clicked.connect(lambda checked=False, e=edit, f=folder: self.browse(e, f))
                column.addWidget(button); self.path_controls.append(button)
            column.addWidget(edit, 1)
            side = len(self.up_buttons)
            up = tool_button(self, f'{label}上移一層', 'imgFolderUp')
            up.clicked.connect(lambda checked=False, s=side: self.navigate_up((s,)))
            column.addWidget(up)
            self.up_buttons.append(up)
            if label == '左側':
                divider = QFrame()
                divider.setObjectName('pathDivider')
                divider.setFrameShape(QFrame.VLine)
                divider.setFrameShadow(QFrame.Plain)
                divider.setLineWidth(1)
                divider.setFixedSize(1, 20)
                column.addWidget(divider)
            path_panes.append(pane)
        bar = QHBoxLayout()
        self.all_button = tool_button(self, '全部檔案（＊）', 'imgFavAll', True)
        self.diff_button = tool_button(self, '僅顯示差異', 'imgFavDiff', True)
        self.same_button = tool_button(self, '相同檔案', 'imgFavSame', True)
        for index, button in enumerate((self.all_button, self.diff_button, self.same_button)):
            button.clicked.connect(lambda checked=False, i=index: self.filter_box.setCurrentIndex(i))
            bar.addWidget(button)
        separator(bar)
        self.compare_button = icon_button(self, '比較／重新整理（F5）', QStyle.SP_BrowserReload)
        self.details_button = tool_button(self, '詳細比較內容（=?；Shift 點擊重新設定）', 'imgCompareContents')
        self.details_button.clicked.connect(self.compare_details)
        self.open_button = icon_button(self, '開啟檔案比較（雙擊檔案）', QStyle.SP_FileDialogDetailedView)
        self.copy_left = icon_button(self, '覆寫到左側', QStyle.SP_ArrowBack)
        self.copy_right = icon_button(self, '覆寫到右側', QStyle.SP_ArrowForward)
        self.sync_left = icon_button(self, '全部同步到左側', QStyle.SP_MediaSeekBackward)
        self.sync_right = icon_button(self, '全部同步到右側', QStyle.SP_MediaSeekForward)
        self.copy_to_button = tool_button(self, '複製選取項目到其他資料夾', 'imgBrowse')
        self.copy_to_button.clicked.connect(self.copy_to_folder)
        for button in (self.compare_button, self.details_button, self.open_button, self.copy_left, self.copy_right, self.sync_left, self.sync_right):
            bar.addWidget(button)
        bar.addWidget(self.copy_to_button)
        separator(bar)
        for title, image, callback in (
            ('展開全部', 'imgExpandAll', self.expand_all),
            ('摺疊全部', 'imgCollapseAll', self.collapse_all),
            ('交換左右', 'imgSwap', self.swap_paths),
        ):
            button = tool_button(self, title, image)
            button.clicked.connect(callback)
            bar.addWidget(button)
        toolbar_buttons = [bar.itemAt(i).widget() for i in range(bar.count())
                           if hasattr(bar.itemAt(i).widget(), 'setToolButtonStyle')]
        bar.addStretch()
        layout.addLayout(bar)
        filters = QHBoxLayout()
        self.filter_box = QComboBox()
        self.filter_box.addItems(['全部檔案', '僅顯示差異', '相同檔案', '僅左側存在', '僅右側存在'])
        self.search = QLineEdit(); self.search.setPlaceholderText('依相對路徑篩選')
        bar.addWidget(self.filter_box); bar.addWidget(self.search, 1)
        self.tree, self.right_tree = QTreeWidget(), QTreeWidget()
        splitter = ComparisonSplitter(self.tree)
        splitter.setObjectName('comparisonSplitter')
        for side, tree in enumerate((self.tree, self.right_tree)):
            tree.setObjectName('folderTree')
            tree.setItemDelegate(FolderSelectionDelegate(tree))
            tree.setStyleSheet('QTreeView::item:selected { background: #DBECF9; }')
            tree.setAlternatingRowColors(True)
            tree.setHeaderLabels(['名稱', '大小', '修改時間'])
            tree.setRootIsDecorated(True)
            tree.setIndentation(15)
            tree.setUniformRowHeights(True)
            tree.setSelectionMode(QTreeWidget.ExtendedSelection)
            tree.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
            tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
            tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
            tree.setColumnWidth(2, 145)
            tree.itemSelectionChanged.connect(lambda s=side: self.sync_selection(s))
            tree.itemExpanded.connect(lambda item, s=side: self.sync_expansion(item, s, True))
            tree.itemCollapsed.connect(lambda item, s=side: self.sync_expansion(item, s, False))
            tree.verticalScrollBar().valueChanged.connect(lambda value, s=side: self.sync_tree_scroll(s, value))
            tree.itemDoubleClicked.connect(lambda item, column: self.open_tree_item(item))
            tree.setContextMenuPolicy(Qt.CustomContextMenu)
            tree.customContextMenuRequested.connect(lambda pos, s=side: self.show_tree_menu(s, pos))
            side_pane = QWidget()
            side_layout = QVBoxLayout(side_pane)
            side_layout.setContentsMargins(0, 0, 0, 0)
            side_layout.setSpacing(2)
            side_layout.addWidget(path_panes[side])
            side_layout.addWidget(tree, 1)
            splitter.addWidget(side_pane)
        self.result_gutter = splitter.handle(1)
        self.result_gutter.bind()
        self.gutter_button_area = QWidget(self.result_gutter)
        self.gutter_button_area.setFixedSize(27, 26)
        self.gutter_button_area.setCursor(Qt.ArrowCursor)
        self.gutter_button_area.installEventFilter(self.result_gutter)
        self.up_both_button = tool_button(self.gutter_button_area, '兩側各上移一層', 'imgBothUp')
        self.up_both_button.setFixedWidth(27)
        self.up_both_button.setCursor(Qt.ArrowCursor)
        self.up_both_button.clicked.connect(lambda: self.navigate_up((0, 1)))
        layout.addWidget(splitter, 1)
        self.summary = QLabel('指定兩個檔案或資料夾後自動比較。雙擊檔案可開啟文字比較。')
        layout.addWidget(self.summary)
        self.compare_button.clicked.connect(self.compare)
        self.open_button.clicked.connect(self.open_selected)
        self.copy_left.clicked.connect(lambda: self.prepare_copy(False))
        self.copy_right.clicked.connect(lambda: self.prepare_copy(True))
        self.sync_left.clicked.connect(lambda: self.prepare_sync(False))
        self.sync_right.clicked.connect(lambda: self.prepare_sync(True))
        self.filter_box.currentIndexChanged.connect(self.render)
        self.search.textChanged.connect(self.render)
        for edit in (self.left_path, self.right_path):
            edit.returnPressed.connect(self.compare)
            edit.textChanged.connect(self.invalidate)
        if host is None:
            QShortcut(QKeySequence('F5'), self, activated=lambda: self.command_target().compare())
        QShortcut(QKeySequence('Return'), self.tree, activated=self.open_selected)
        QShortcut(QKeySequence('Return'), self.right_tree, activated=self.open_selected)
        self.create_menus()
        self.tabs.currentChanged.connect(self.update_current_tab)
        from lib.ui.font_settings import FontSettings
        self.apply_fonts(FontSettings())
        for button, caption in zip(toolbar_buttons, (
            '全部', '差異', '相同', '重新整理', '詳細比較', '開啟比較',
            '複製到左', '複製到右', '同步到左', '同步到右', '複製到…',
            '展開全部', '摺疊全部', '交換左右',
        )):
            button.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            button.setText(caption)
            button.setToolTip('')
            button.ensurePolished()
            button.setFixedSize(max(40, button.fontMetrics().horizontalAdvance(caption) + 14), 46)
        self.left_path.setFocus()
        self.update_controls()

    def invalidate(self):
        if self.compared_paths != self.paths():
            self.rows = []; self.compared_paths = None
            self.render()
            self.refresh_timer.stop()
            self._refresh_pending = False
            watched = self.watcher.files() + self.watcher.directories()
            if watched: self.watcher.removePaths(watched)
            if all(self.paths()):
                self.request_refresh()
            else:
                self.summary.setText('請指定兩側的檔案或資料夾，指定完成後自動比較。')
        self.update_controls()

    def paths(self):
        return self.left_path.text().strip().strip('"'), self.right_path.text().strip().strip('"')

    def browse(self, edit, folder):
        if self.busy: return
        path = QFileDialog.getExistingDirectory(self, '選擇資料夾', edit.text()) if folder else QFileDialog.getOpenFileName(self, '選擇檔案', edit.text())[0]
        if path: edit.setText(path)

    def parent_paths(self):
        parents = []
        for value in self.paths():
            try:
                path = Path(value).resolve() if value else None
                parent = path.parent if path is not None and path.is_dir() else None
                parents.append(parent if parent is not None and parent != path else None)
            except OSError:
                parents.append(None)
        return parents

    def navigate_up(self, sides):
        if self.busy: return
        parents = self.parent_paths()
        if any(parents[side] is None for side in sides): return
        for side in sides:
            (self.left_path, self.right_path)[side].setText(str(parents[side]))
        if all(self.paths()): self.compare()

    def update_controls(self):
        ready = not self.busy and self.compared_paths == self.paths()
        for button in (self.details_button, self.open_button, self.copy_left, self.copy_right, self.sync_left, self.sync_right, self.copy_to_button):
            button.setEnabled(ready)
        for control in (self.compare_button, self.left_path, self.right_path, *self.path_controls):
            control.setEnabled(not self.busy)
        for action in (self.shell_register_action, self.shell_unregister_action):
            action.setEnabled(not self.busy)
        parents = self.parent_paths()
        for side, button in enumerate(self.up_buttons):
            button.setEnabled(not self.busy and parents[side] is not None)
            label = '左側' if side == 0 else '右側'
            button.setToolTip(f'{label}上移至 {parents[side]}' if parents[side] is not None else f'{label}無法上移')
        self.up_both_button.setEnabled(not self.busy and all(parent is not None for parent in parents))
        self.up_both_button.setToolTip(f'兩側各上移一層\n左側：{parents[0]}\n右側：{parents[1]}'
            if all(parent is not None for parent in parents) else '兩側無法同時上移')
        self.close_tab_action.setEnabled(self.tabs.count() > 0 and
            (not self.busy or self.tabs.currentWidget() is not self.folder_tab))
        if self.host is not None: self.host.update_controls()

    def run_job(self, operation, callback):
        if self.busy: return
        self.busy = True; self.update_controls()
        worker = Worker(operation, self)
        self.workers.append(worker)
        worker.result.connect(callback)
        worker.failed.connect(lambda message: msgCritical('操作未完成', message, self))
        worker.finished.connect(lambda: self.finish_job(worker))
        worker.start()

    def finish_job(self, worker):
        self.busy = False
        self.workers.remove(worker); worker.deleteLater()
        self.update_controls()
        if self._refresh_pending: self.refresh_timer.start(0)
        self.process_file_requests()

    def request_refresh(self, *_):
        if self._closing: return
        self._refresh_pending = True
        self.refresh_timer.start(200)

    def invalidate_content(self, changed):
        self._content_epoch += 1
        path = Path(changed).resolve()
        for index, row in enumerate(self.rows):
            if any(path == item.resolve() or path in item.resolve().parents for item in (row.left, row.right)):
                self.rows[index] = replace(row, verified=False)
        self.request_refresh()

    def refresh_if_ready(self):
        if self.busy or self._confirmation_active or self._closing: return
        self._refresh_pending = False
        if not all(self.paths()):
            clean = [(window, window.file_pair, window.disk_baseline)
                     for window in self.windows if not any(window.dirty)]
            if not clean: return
            def operation():
                result = []
                for window, pair, baseline in clean:
                    try:
                        updated = load_binary_comparison(pair) if isinstance(window, HexCompare) else [TextFile.load(path) if path.exists() else None for path in pair]
                    except (OSError, ValueError): updated = None
                    result.append((window, updated, baseline))
                return result
            def complete(result):
                for window, updated, baseline in result:
                    if window in self.windows: window.apply_disk_update(updated, baseline)
                self.update_watches()
            self.run_job(operation, complete)
            return
        try:
            roots(*self.paths())
        except (ValueError, OSError):
            self.compared_paths = None
            self.summary.setText('請指定兩個存在且同類型的檔案或資料夾，路徑不得相同或互相包含。')
            self.update_controls()
            return
        self.compare()

    def update_watches(self):
        wanted = {str(Path(path).resolve()) for path in self.paths() if path and Path(path).exists()}
        for window in self.windows:
            for path in window.file_pair:
                if path.exists(): wanted.add(str(path))
                if path.parent.exists(): wanted.add(str(path.parent))
        for row in self.rows:
            for path in (row.left, row.right):
                if path.exists(): wanted.add(str(path))
        current = set(self.watcher.files()) | set(self.watcher.directories())
        if current - wanted: self.watcher.removePaths(list(current - wanted))
        if wanted - current:
            failed = self.watcher.addPaths(list(wanted - current))
            if failed: self.summary.setText(self.summary.text() + f'　{len(failed)} 個路徑無法監看，可按 F5 更新')

    def compare(self):
        if self.busy: return
        paths = self.paths()
        if not all(paths):
            msgInfo('尚未選擇路徑', '請選擇左右兩側的檔案或資料夾。', self); return
        self.refresh_timer.stop()
        self._refresh_pending = False
        self.compared_paths = None
        self.pending_documents = None
        expanded = {name for name, pair in self.item_pairs.items() if pair[0].isExpanded()}
        selected = {row.relative for row in self.selected()}
        scroll = self.tree.verticalScrollBar().value()
        clean_windows = [(window, window.file_pair, window.disk_baseline)
                         for window in self.windows if not any(window.dirty)]
        verified = {(row.left.resolve(), row.right.resolve()): row for row in self.rows if row.verified}
        content_epoch = self._content_epoch
        self.summary.setText('正在快速比較大小與修改時間…')
        def operation():
            rows = compare_paths(*paths)
            documents = None
            if self.auto_open_files and all(Path(path).is_file() for path in paths):
                candidates = [TextFile.load(path) for path in paths]
                if all(doc is not None for doc in candidates): documents = candidates
            reloads = []
            for window, pair, baseline in clean_windows:
                try:
                    if isinstance(window, HexCompare):
                        updated = load_binary_comparison(pair)
                    else: updated = [TextFile.load(path) if path.exists() else None for path in pair]
                except OSError: updated = None
                reloads.append((window, updated, baseline))
            return rows, documents, reloads
        def complete(result):
            if paths != self.paths():
                self.request_refresh()
                return
            rows, self.pending_documents, reloads = result
            if content_epoch == self._content_epoch:
                for index, row in enumerate(rows):
                    previous = verified.get((row.left.resolve(), row.right.resolve()))
                    if previous is not None and previous.stamp == row.stamp:
                        rows[index] = replace(row, status=previous.status, verified=True)
            self.rows, self.compared_paths = rows, paths
            self.render()
            self._syncing_tree = True
            for name, pair in self.item_pairs.items():
                for item in pair:
                    item.setExpanded(name in expanded)
                    item.setSelected(name in selected)
            self.tree.verticalScrollBar().setValue(scroll)
            self.right_tree.verticalScrollBar().setValue(scroll)
            self._syncing_tree = False
            self.update_watches()
            for window, updated, baseline in reloads:
                if window in self.windows: window.apply_disk_update(updated, baseline)
        self.run_job(operation, complete)
        if self.auto_open_files: self.workers[-1].finished.connect(self.open_auto_pair)

    def open_auto_pair(self):
        if not self.rows or not all(Path(path).is_file() for path in self.paths()): return
        self.tree.setCurrentItem(self.tree.topLevelItem(0))
        self.open_selected()

    def compare_details(self):
        if self.busy or self.compared_paths != self.paths(): return
        selected = {row.relative for row in self.selected()} or None
        from lib.ui.compare_options import CompareOptions
        dialog = CompareOptions(self.rows, selected, self)
        self._confirmation_active = True
        try:
            if (not dialog.skip_box.isChecked() or QApplication.keyboardModifiers() & Qt.ShiftModifier):
                if dialog.exec() != QDialog.Accepted: return
            method, rules, show_results = dialog.options()
        finally:
            dialog.deleteLater()
            self._confirmation_active = False
            if self._refresh_pending: self.refresh_timer.start(0)
        expanded = {name for name, pair in self.item_pairs.items() if pair[0].isExpanded()}
        scroll = self.tree.verticalScrollBar().value()
        snapshot = list(self.rows)
        self.summary.setText('正在詳細比較內容…')
        def complete(rows):
            self.rows = rows
            self.render()
            self._syncing_tree = True
            for name, pair in self.item_pairs.items():
                for item in pair:
                    item.setExpanded(name in expanded)
                    item.setSelected(selected is not None and name in selected)
            self.tree.verticalScrollBar().setValue(scroll)
            self.right_tree.verticalScrollBar().setValue(scroll)
            self._syncing_tree = False
            if show_results:
                checked = [row for row in rows if not row.directory and row.verified and
                    (selected is None or row.relative in selected or any(row.relative.startswith(name + '/') for name in selected))]
                same = sum(row.status == 'same' for row in checked)
                self._confirmation_active = True
                try: msgInfo('比較結果', f'已檢查 {len(checked)} 個檔案：相同 {same}，不同 {len(checked) - same}。', self)
                finally:
                    self._confirmation_active = False
                    if self._refresh_pending: self.refresh_timer.start(0)
        self.run_job(lambda: verify_contents(snapshot, selected, method, rules), complete)

    def render(self, *_):
        self._syncing_tree = True
        self.tree.clear(); self.right_tree.clear(); self.item_pairs.clear()
        choice, query = self.filter_box.currentIndex(), self.search.text().casefold()
        for index, button in enumerate((self.all_button, self.diff_button, self.same_button)):
            button.setChecked(index == choice)
        matched = []
        for row in self.rows:
            if query not in row.relative.casefold(): continue
            if choice == 1 and row.status == 'same': continue
            if choice == 2 and row.status != 'same': continue
            if choice == 3 and row.status != 'left': continue
            if choice == 4 and row.status != 'right': continue
            matched.append(row)
        by_name = {row.relative: row for row in self.rows}
        folder_styles, folder_sizes = summarize_folders(self.rows)
        names = {row.relative for row in matched}
        for name in tuple(names):
            names.update(parent.as_posix() for parent in Path(name).parents if parent.as_posix() != '.')
        for name in sorted(names, key=lambda n: (len(Path(n).parts), n.casefold())):
            row = by_name[name]
            pair = []
            parent_name = Path(name).parent.as_posix()
            for side, (tree, path, size) in enumerate(((self.tree, row.left, row.left_size), (self.right_tree, row.right, row.right_size))):
                exists = path.exists()
                try:
                    modified = datetime.fromtimestamp(path.stat().st_mtime).strftime('%Y/%m/%d %H:%M') if exists else ''
                except OSError:
                    modified = ''
                is_folder = exists and row.directory and path.is_dir()
                if is_folder: size = folder_sizes[name][side]
                item = QTreeWidgetItem([Path(name).name if exists else '', self.size(size) if exists else '', modified])
                item.setData(0, Qt.UserRole, row)
                item.setData(0, Qt.UserRole + 1, name)
                color = file_color(row, side)
                for column in range(3):
                    item.setForeground(column, QColor(('#000000' if column == 0 else '#808080') if is_folder else color))
                description = STATUS[row.status]
                if is_folder: description = FOLDER_DESCRIPTIONS[folder_styles[name][side]]
                if not row.directory and row.status in ('same', 'different'):
                    description = ('內容' if row.verified else '資訊') + ('相同' if row.status == 'same' else '不同')
                    if not row.verified: description += '（未檢查內容）'
                item.setToolTip(0, f'{path}\n{description}')
                if exists:
                    icon = 'imgFolder_' + folder_styles[name][side] if is_folder else {
                        '#000000': 'imgFile_same', '#ff0000': 'imgFile_red',
                        '#808080': 'imgFile_gray', '#285b83': 'imgFile_purple',
                    }[color]
                    item.setIcon(0, app_icon(icon))
                if parent_name in self.item_pairs:
                    self.item_pairs[parent_name][side].addChild(item)
                else:
                    tree.addTopLevelItem(item)
                pair.append(item)
            self.item_pairs[name] = pair
        self._syncing_tree = False
        files = [row for row in self.rows if not row.directory]
        same = sum(row.status == 'same' for row in files)
        verified = sum(row.status == 'same' and row.verified for row in files)
        self.summary.setText(f'{len(files)} 個檔案　資訊相同 {same - verified}　內容相同 {verified}　差異 {len(files) - same}　大小：位元組　=? 檢查內容')
        self.update_controls()

    def sync_selection(self, side):
        if self._syncing_tree: return
        self.active_tree_side = side
        self._syncing_tree = True
        source, target = (self.tree, self.right_tree) if side == 0 else (self.right_tree, self.tree)
        target.clearSelection()
        for item in source.selectedItems():
            name = item.data(0, Qt.UserRole + 1)
            self.item_pairs[name][1 - side].setSelected(True)
        self._syncing_tree = False

    def sync_expansion(self, item, side, expanded):
        if self._syncing_tree: return
        self._syncing_tree = True
        pair = self.item_pairs.get(item.data(0, Qt.UserRole + 1))
        if pair: pair[1 - side].setExpanded(expanded)
        self._syncing_tree = False

    def sync_tree_scroll(self, side, value):
        if self._syncing_tree: return
        self._syncing_tree = True
        (self.right_tree if side == 0 else self.tree).verticalScrollBar().setValue(value)
        self._syncing_tree = False

    def expand_all(self):
        self.tree.expandAll(); self.right_tree.expandAll()

    def collapse_all(self):
        self.tree.collapseAll(); self.right_tree.collapseAll()

    def swap_paths(self):
        if self.busy or self.has_pending_edits(): return
        left, right = self.paths()
        self.left_path.setText(right); self.right_path.setText(left)
        if left and right: self.compare()

    def open_tree_item(self, item):
        row = item.data(0, Qt.UserRole)
        if row.directory: return
        self.open_selected()

    def create_menus(self):
        def add(menu, title, callback, shortcut=None):
            action = QAction(title, self)
            if shortcut and self.host is None: action.setShortcut(shortcut)
            action.triggered.connect(lambda checked=False: self.invoke_command(callback))
            menu.addAction(action)
            return action
        session = self.menuBar().addMenu('工作階段')
        add(session, '資料夾比較', self.show_folder_tab)
        self.close_tab_action = add(session, '關閉目前分頁', lambda: self.close_tab(self.tabs.currentIndex()), 'Ctrl+W')
        add(session, '結束', self.close)
        file_menu = self.menuBar().addMenu('檔案')
        add(file_menu, '開啟比較', self.open_selected)
        add(file_menu, '儲存左側', lambda: self.save_current(0))
        add(file_menu, '儲存右側', lambda: self.save_current(1))
        add(file_menu, '儲存目前側', lambda: self.text_command('save_side'), 'Ctrl+S')
        add(file_menu, '左側另存新檔…', lambda: self.text_command('save_as', 0))
        add(file_menu, '右側另存新檔…', lambda: self.text_command('save_as', 1))
        add(file_menu, '目前側另存新檔…', lambda: self.text_command('save_as'), 'Ctrl+Shift+S')
        operations = self.menuBar().addMenu('動作')
        add(operations, '複製到左側', lambda: self.command_target().copy_current(False))
        add(operations, '複製到右側', lambda: self.command_target().copy_current(True))
        add(operations, '複製到其他資料夾…', self.copy_to_folder)
        add(operations, '詳細比較內容（=?）', self.compare_details)
        edit = self.menuBar().addMenu('編輯')
        add(edit, '復原', lambda: self.history_current(False), 'Ctrl+Z')
        add(edit, '取消復原', lambda: self.history_current(True), 'Ctrl+Y')
        integration = self.menuBar().addMenu('整合')
        self.shell_register_action = QAction('註冊右鍵整合', self)
        self.shell_unregister_action = QAction('取消註冊右鍵整合', self)
        self.shell_register_action.triggered.connect(lambda: self.toggle_shell(True))
        self.shell_unregister_action.triggered.connect(lambda: self.toggle_shell(False))
        integration.addActions([self.shell_register_action, self.shell_unregister_action])
        view = self.menuBar().addMenu('檢視')
        for index, title in enumerate(('全部', '差異', '相同')):
            add(view, title, lambda checked=False, i=index: self.command_target().set_filter(i))
        add(view, '展開全部', self.expand_all)
        add(view, '摺疊全部', self.collapse_all)
        add(view, '字型設定…', self.configure_fonts)
        search = self.menuBar().addMenu('搜尋')
        add(search, '搜尋', self.focus_search, 'Ctrl+F')
        add(search, '搜尋與取代…', lambda: self.text_command('show_replace', with_side=False), 'Ctrl+H')

    def command_target(self):
        return self

    def invoke_command(self, callback):
        target = self.command_target()
        if getattr(callback, '__self__', None) is self and callback.__name__ in (
                'open_selected', 'copy_to_folder', 'compare_details', 'expand_all',
                'collapse_all', 'focus_search'):
            getattr(target, callback.__name__)()
        else:
            callback()

    def text_command(self, command, side=None, with_side=True):
        current = self.tabs.currentWidget()
        if isinstance(current, TextCompare):
            method = getattr(current, command)
            method(current.active_side if side is None else side) if with_side else method()

    def history_current(self, redo):
        current = self.tabs.currentWidget()
        if isinstance(current, TextCompare):
            current.redo() if redo else current.undo()

    def apply_fonts(self, settings):
        self.font_settings = settings
        style = APP_STYLE + settings.stylesheet()
        app = QApplication.instance()
        if app.styleSheet() != style: app.setStyleSheet(style)
        for window in self.windows:
            if isinstance(window, TextCompare):
                for editor in (window.left_edit, window.right_edit): editor.update_margin()
            elif isinstance(window, HexCompare): window.resize_columns()

    def configure_fonts(self):
        from lib.ui.font_settings import FontDialog
        dialog = FontDialog(self.font_settings, self)
        if dialog.exec() == QDialog.Accepted:
            settings = dialog.values()
            try:
                settings.save(); self.apply_fonts(settings)
            except OSError as error: msgCritical('無法儲存字型設定', str(error), self)
        dialog.deleteLater()

    def toggle_shell(self, enabled):
        if self.busy: return
        text = '加入 DualMirror 的 Windows 11 第一層右鍵整合？\n支援選為左側比較及直接比較兩個項目。\n僅註冊目前帳號，會取代舊版整合。' if enabled else '取消目前帳號的 DualMirror 右鍵註冊？\n一併移除舊版整合，保留字型與比較設定。'
        if not confirmBox('右鍵整合', text, default_confirm=False, parent=self): return
        if self.busy: return
        from lib.integration.shell_integration import install, uninstall
        message = '已註冊右鍵整合。' if enabled else '已取消註冊右鍵整合。'
        self.run_job(install if enabled else uninstall, lambda _: self.summary.setText(message))

    def focus_search(self):
        current = self.tabs.currentWidget()
        if isinstance(current, TextCompare): current.show_find()
        else: self.search.setFocus()

    def save_current(self, side):
        current = self.tabs.currentWidget()
        if isinstance(current, TextCompare): current.save_side(side)

    def copy_current(self, to_right):
        current = self.tabs.currentWidget()
        if isinstance(current, TextCompare): current.copy_block('right' if to_right else 'left')
        elif isinstance(current, HexCompare):
            if self.busy or self.has_pending_edits(): return
            source, target = current.file_pair if to_right else tuple(reversed(current.file_pair))
            self.prepare_plan(lambda: [make_action(source, target)])
        else: self.prepare_copy(to_right)

    def set_filter(self, index):
        current = self.tabs.currentWidget()
        if isinstance(current, TextCompare): current.set_filter(index)
        else: self.filter_box.setCurrentIndex(index)

    @staticmethod
    def size(value):
        return f'{value:,}' if value is not None else '—'

    def selected(self):
        return [item.data(0, Qt.UserRole) for item in self.tree.selectedItems()]

    def show_tree_menu(self, side, pos):
        tree = (self.tree, self.right_tree)[side]
        item = tree.itemAt(pos)
        if item is None or self.busy: return
        if not item.isSelected():
            tree.clearSelection(); item.setSelected(True)
        self.active_tree_side = side
        menu = QMenu(self)
        for title, callback in (
            ('開啟比較', self.open_selected),
            ('複製到另一側', lambda: self.prepare_copy(side == 0)),
            ('複製到指定資料夾…', self.copy_to_folder),
            ('重新命名…', self.rename_selected),
            ('刪除（移至資源回收筒）…', self.delete_selected),
        ):
            action = menu.addAction(title)
            action.triggered.connect(callback)
        menu.exec(tree.viewport().mapToGlobal(pos))
        menu.deleteLater()

    def action_paths(self):
        from lib.core.file_actions import selected_paths
        if self.busy or self.compared_paths != self.paths() or self.has_pending_edits(): return []
        side = self.active_tree_side
        paths = [row.left if side == 0 else row.right for row in self.selected()]
        return selected_paths(self.paths()[side], paths)

    def rename_selected(self):
        from lib.core.file_actions import rename_item, identity, unchanged
        try:
            paths = self.action_paths()
            if len(paths) != 1:
                if paths: msgInfo('重新命名', '請只選取一個檔案或資料夾。', self)
                return
            source = paths[0]
            stamps = [identity(source)]
            side = self.active_tree_side
            dialog = QInputDialog(self)
            dialog.setWindowTitle('重新命名')
            dialog.setLabelText(f'新名稱（僅變更目前側）：\n{source}')
            dialog.setTextValue(source.name)
            dialog.setOkButtonText('重新命名'); dialog.setCancelButtonText('取消')
            self._confirmation_active = True
            try:
                accepted = dialog.exec() == QDialog.Accepted
            finally:
                self._confirmation_active = False
                if self._refresh_pending: self.refresh_timer.start(0)
            if accepted:
                name = dialog.textValue()
                def operation():
                    unchanged(paths, stamps)
                    return rename_item(source, name)
                def complete(target):
                    if Path(self.paths()[side]) == source:
                        (self.left_path, self.right_path)[side].setText(str(target))
                    self.request_refresh()
                self.run_job(operation, complete)
                self.workers[-1].finished.connect(self.request_refresh)
            dialog.deleteLater()
        except Exception as error: msgCritical('無法重新命名', str(error), self)

    def delete_selected(self):
        from lib.core.file_actions import recycle_items, identity, unchanged
        try:
            paths = self.action_paths()
            if not paths: return
            stamps = [identity(path) for path in paths]
            side = '左側' if self.active_tree_side == 0 else '右側'
            self._confirmation_active = True
            try:
                accepted = confirmBox('確認刪除',
                    f'將{side}選取的 {len(paths)} 個項目移至資源回收筒？\n資料夾包含其中所有內容，另一側不變。',
                    confirm_text='移至資源回收筒', default_confirm=False, parent=self)
            finally:
                self._confirmation_active = False
                if self._refresh_pending: self.refresh_timer.start(0)
            if accepted:
                def operation():
                    unchanged(paths, stamps)
                    recycle_items(paths)
                self.run_job(operation, lambda _: self.request_refresh())
                self.workers[-1].finished.connect(self.request_refresh)
        except Exception as error: msgCritical('無法刪除', str(error), self)

    def open_selected(self):
        if self.busy or self.compared_paths != self.paths(): return
        rows = self.selected()
        if len(rows) != 1:
            msgInfo('選擇檔案', '請選取一個檔案。', self); return
        row = rows[0]
        if row.directory or row.status == 'conflict':
            msgInfo('無法開啟文字比較', '請選取檔案；資料夾或同名類型衝突無法開啟文字比較。', self); return
        self.pending_documents = None
        self.open_file_pair((row.left, row.right), allow_missing=True)

    def add_comparison_tab(self, window, pair):
        if self.host is not None:
            self.host.add_comparison_tab(window, pair)
            return
        window.file_pair = pair
        self.windows.append(window)
        window.destroyed.connect(lambda: self.windows.remove(window) if window in self.windows else None)
        window.saved.connect(self.request_refresh)
        if isinstance(window, TextCompare):
            window.path_requested.connect(lambda side, path: self.replace_comparison_path(window, side, path))
        index = self.tabs.addTab(window, app_icon('imgTextCompareSession'), pair[0].name)
        self.tabs.setTabToolTip(index, f'{pair[0]}\n{pair[1]}')
        self.tabs.setCurrentIndex(index)
        if isinstance(window, HexCompare):
            window.compared.connect(lambda: self.publish_hex_result(window))
            self.publish_hex_result(window)

    def open_startup_pair(self, pair):
        if all(Path(path).is_file() for path in pair):
            self.tabs.removeTab(self.tabs.indexOf(self.folder_tab))
            self.open_file_pair(pair)
        else:
            self.left_path.setText(str(pair[0])); self.right_path.setText(str(pair[1]))
            self.compare()

    def open_file_pair(self, pair, replacing=None, allow_missing=False):
        """排入背景載入，驗證成功並確認捨棄後才替換舊分頁。"""
        if self.host is not None:
            self.host.open_file_pair(pair, replacing, allow_missing)
            return
        try:
            pair = tuple(Path(path).resolve() for path in pair)
            if len(pair) != 2 or (not allow_missing and not all(path.is_file() for path in pair)):
                raise ValueError('請指定兩個存在的檔案。')
            if allow_missing and (not any(path.is_file() for path in pair) or
                                  any(path.exists() and not path.is_file() for path in pair)):
                raise ValueError('請指定檔案配對。')
            if pair[0] == pair[1]:
                raise ValueError('左右兩側不得指定相同檔案。')
            if replacing is not None and pair == replacing.file_pair: return
            request = (pair, replacing, allow_missing)
            if request == self._loading_request or request in self._file_requests: return
            self._file_requests.append(request)
            self.process_file_requests()
        except Exception as error:
            msgInfo('檔案比較', str(error), self)

    def process_file_requests(self):
        if self.busy or self._loading_request is not None or self._confirmation_active or self._closing: return
        while self._file_requests:
            request = self._file_requests.pop(0)
            pair, replacing, allow_missing = request
            if replacing is not None and replacing not in self.windows: continue
            if any(page.file_pair == pair for page in self.windows):
                self.complete_file_request(request, None)
                if self.busy or self._confirmation_active: return
                continue
            self._loading_request = request
            self.summary.setText('正在讀取並比較檔案…')
            def operation(pair=pair, allow_missing=allow_missing):
                before = pair_stamp(*pair)
                if not allow_missing and not all(path.is_file() for path in pair):
                    raise ValueError('請指定兩個存在的檔案。')
                docs = [TextFile.load(path) if path.exists() else None for path in pair]
                binary = None
                blocks = None
                if any(doc is None and path.exists() for doc, path in zip(docs, pair)):
                    binary = load_binary_comparison(pair)
                else:
                    blocks = differences(*(doc.text if doc is not None else '' for doc in docs))
                if pair_stamp(*pair) != before: raise OSError('檔案在讀取期間已變更，請重新開啟。')
                return docs, blocks, binary, before
            self.run_job(operation, lambda result, r=request: self.complete_file_request(r, result))
            self.workers[-1].finished.connect(lambda r=request: self.finish_file_request(r))
            return

    def finish_file_request(self, request):
        if self._loading_request == request: self._loading_request = None
        self.process_file_requests()

    def complete_file_request(self, request, result):
        pair, replacing, _ = request
        candidate = None
        self._confirmation_active = True
        try:
            if self._closing or (replacing is not None and replacing not in self.windows): return
            existing = next((item for item in self.windows if item.file_pair == pair), None)
            if existing is None:
                docs, blocks, binary, stamp = result
                if pair_stamp(*pair) != stamp: raise OSError('檔案在讀取後已變更，請重新開啟。')
                if binary is not None:
                    data, alignment, stamp = binary
                    candidate = HexCompare(*pair, self.tabs, documents=data, alignment=alignment, stamp=stamp)
                else:
                    candidate = TextCompare(*pair, self.tabs, documents=docs, initial_blocks=blocks)
            old_index = self.tabs.indexOf(replacing) if replacing is not None else -1
            if replacing is not None:
                if isinstance(replacing, TextCompare): replacing.flush_edit()
                if not replacing.close():
                    if candidate is not None: candidate.deleteLater()
                    return
                self.tabs.removeTab(old_index)
                self.windows.remove(replacing)
                replacing.deleteLater()
            if existing is not None:
                self.tabs.setCurrentWidget(existing)
            else:
                self.add_comparison_tab(candidate, pair)
                if old_index >= 0:
                    self.tabs.tabBar().moveTab(self.tabs.indexOf(candidate), old_index)
            self.update_watches()
            self.update_current_tab()
        except Exception as error:
            if candidate is not None and candidate not in self.windows: candidate.deleteLater()
            msgInfo('檔案比較', str(error), self)
        finally:
            self._confirmation_active = False
            if self._refresh_pending: self.refresh_timer.start(0)
            self.process_file_requests()

    def replace_comparison_path(self, window, side, path):
        if window not in self.windows: return
        pair = list(window.file_pair)
        pair[side] = path
        self.open_file_pair(pair, replacing=window)

    def publish_hex_result(self, window):
        if window.stamp is None: return
        if any(data is None for data in window.documents): return
        if pair_stamp(*window.file_pair) != window.stamp: return
        changed = False
        for index, row in enumerate(self.rows):
            if (row.left.resolve(), row.right.resolve()) != window.file_pair: continue
            if row.stamp != window.stamp: continue
            self.rows[index] = replace(row, status='different' if window.blocks else 'same', verified=True)
            changed = True
        if not changed: return
        expanded = {name for name, pair in self.item_pairs.items() if pair[0].isExpanded()}
        selected = {row.relative for row in self.selected()}
        scroll = self.tree.verticalScrollBar().value()
        self.render()
        self._syncing_tree = True
        for name, pair in self.item_pairs.items():
            for item in pair:
                item.setExpanded(name in expanded); item.setSelected(name in selected)
        self.tree.verticalScrollBar().setValue(scroll)
        self.right_tree.verticalScrollBar().setValue(scroll)
        self._syncing_tree = False

    def show_folder_tab(self):
        if self.tabs.indexOf(self.folder_tab) < 0:
            self.tabs.insertTab(0, self.folder_tab, app_icon('imgDirCompareSession'), '資料夾比較')
        self.tabs.setCurrentWidget(self.folder_tab)
        self.update_current_tab()
        self.left_path.setFocus()

    def update_current_tab(self, *_):
        self.workspace.setCurrentWidget(self.tabs if self.tabs.count() else self.home)
        self.update_controls()

    def close_tab(self, index):
        if index < 0: return
        window = self.tabs.widget(index)
        if window is self.folder_tab:
            if self.busy: return
            self.auto_open_files = False
            self.pending_documents = None
            for edit in (self.left_path, self.right_path):
                edit.blockSignals(True)
                edit.clear()
                edit.blockSignals(False)
            self.invalidate()
            self.search.clear()
            self.filter_box.setCurrentIndex(0)
            self.tabs.removeTab(index)
            self.update_current_tab()
            return
        if window is None or not window.close(): return
        self.tabs.removeTab(index)
        if window in self.windows: self.windows.remove(window)
        window.deleteLater()
        self.update_current_tab()

    def has_pending_edits(self):
        if self.host is not None: return self.host.has_pending_edits()
        if any(any(window.dirty) for window in self.windows):
            msgInfo('尚有未儲存變更', '請先儲存或關閉文字比較視窗，再執行覆寫或同步。', self)
            return True
        return False

    def prepare_copy(self, to_right):
        if self.busy or self.compared_paths != self.paths() or self.has_pending_edits(): return
        rows = self.selected()
        if not rows:
            msgInfo('選擇檔案', '請先選取要複製的檔案，可使用 Ctrl 或 Shift 多選。', self); return
        snapshot = list(self.rows)
        def build():
            chosen = {row.relative for row in rows}
            folders = [row.relative + '/' for row in rows if row.directory]
            plan = []
            for row in sorted(snapshot, key=lambda row: (len(Path(row.relative).parts), row.relative)):
                if row.relative not in chosen and not any(row.relative.startswith(folder) for folder in folders): continue
                source, target = (row.left, row.right) if to_right else (row.right, row.left)
                if not source.exists():
                    if row.relative in chosen: raise ValueError(f'來源不存在：{source}')
                    continue
                action = make_action(source, target)
                if action.source_hash != action.target_hash: plan.append(action)
            return plan
        self.prepare_plan(build)

    def copy_to_folder(self):
        if self.busy or self.compared_paths != self.paths() or self.has_pending_edits(): return
        rows = self.selected()
        if not rows:
            msgInfo('選取項目', '請先選取要複製的檔案或資料夾。', self); return
        destination = QFileDialog.getExistingDirectory(self, '選擇複製目的資料夾')
        if not destination: return
        sources = [row.left if self.active_tree_side == 0 else row.right for row in rows]
        self.prepare_plan(lambda: selection_plan(sources, Path(destination)))

    def prepare_plan(self, operation):
        if self.busy: return
        self.pending_plan = None
        self.summary.setText('正在準備複製清單…')
        self.run_job(operation, lambda plan: setattr(self, 'pending_plan', plan))
        self.workers[-1].finished.connect(self.show_pending_plan)

    def prepare_sync(self, to_right):
        if self.busy or self.compared_paths != self.paths() or self.has_pending_edits(): return
        paths = self.paths() if to_right else tuple(reversed(self.paths()))
        self.summary.setText('正在準備同步清單…')
        # 預覽須等背景工作結束，避免確認後被 busy 擋住。
        self.prepare_plan(lambda: sync_plan(*paths))

    def show_pending_plan(self):
        if self.pending_plan is not None:
            self.preview(self.pending_plan)
            self.pending_plan = None

    def preview(self, plan):
        if self.busy: return
        if not plan:
            msgInfo('無需同步', '來源檔案都已相同；目的端多出的檔案已保留。', self); return
        added = sum(action.target_hash is None for action in plan)
        self._confirmation_active = True
        try:
            accepted = confirmBox('確認覆寫與同步',
                f'處理 {len(plan)} 個項目：新增 {added}，覆寫 {len(plan) - added}。\n來源與目的端多出的檔案均會保留。是否執行？',
                confirm_text='確認執行', default_confirm=False, parent=self)
        finally:
            self._confirmation_active = False
            if self._refresh_pending: self.refresh_timer.start(0)
        if not accepted: return
        self.summary.setText('正在寫入檔案，請勿關閉程式…')
        def complete(count):
            self.summary.setText(f'已完成 {count} 個項目，正在更新比較結果…')
            self.request_refresh()
        self.run_job(lambda: execute_plan(plan), complete)

    def closeEvent(self, event):
        if self.busy:
            msgInfo('工作進行中', '請等待目前工作完成後再關閉。', self); event.ignore(); return
        for window in list(self.windows):
            if not window.close(): event.ignore(); return
        self._closing = True
        self._refresh_pending = False
        self.refresh_timer.stop()
        self.watcher.blockSignals(True)
        watched = self.watcher.files() + self.watcher.directories()
        if watched: self.watcher.removePaths(watched)
        event.accept()


class MainWindow(ComparisonSession):
    """單一主視窗；額外的資料夾比較元件直接嵌入外層分頁。"""

    def __init__(self):
        self.folder_sessions = []
        super().__init__()
        self.folder_sessions.append(self)
        from lib.ui.file_drop import FileDropFilter
        self.file_drop_filter = FileDropFilter(self)

    def command_target(self):
        current = self.tabs.currentWidget()
        return current if isinstance(current, ComparisonSession) else self

    def update_controls(self):
        super().update_controls()
        current = self.tabs.currentWidget()
        owner = self if current is self.folder_tab else current
        self.close_tab_action.setEnabled(self.tabs.count() > 0 and
            not (isinstance(owner, ComparisonSession) and owner.busy))

    def show_folder_tab(self):
        if not all(self.paths()):
            super().show_folder_tab()
            return
        self.new_folder_session()

    def new_folder_session(self):
        session = ComparisonSession(self)
        session.setWindowFlags(Qt.Widget)
        session.menuBar().hide()
        session.tabs.tabBar().hide()
        # 外層分頁負責關閉，內層只承載這組比較原有的工具列和資料樹。
        session.tabs.setTabsClosable(False)
        self.folder_sessions.append(session)
        self.tabs.addTab(session, app_icon('imgDirCompareSession'), '資料夾比較')
        self.tabs.setCurrentWidget(session)
        session.show()
        return session

    def open_request(self, paths):
        """接收另一次啟動；保留所有現有工作與未儲存內容。"""
        if paths:
            try:
                if len(paths) != 2: raise ValueError('請指定兩個比較路徑。')
                pair = tuple(Path(path).resolve() for path in paths)
                roots(*pair)
                if all(path.is_file() for path in pair):
                    self.open_file_pair(pair)
                else:
                    session = next((item for item in self.folder_sessions
                        if all(item.paths()) and tuple(Path(p).resolve() for p in item.paths()) == pair), None)
                    if session is None:
                        if not all(self.paths()) and self.tabs.indexOf(self.folder_tab) >= 0:
                            session = self
                        else:
                            session = self.new_folder_session()
                        session.left_path.setText(str(pair[0]))
                        session.right_path.setText(str(pair[1]))
                        session.compare()
                    page = self.folder_tab if session is self else session
                    self.tabs.setCurrentWidget(page)
                    index = self.tabs.indexOf(page)
                    self.tabs.setTabText(index, pair[0].name)
                    self.tabs.setTabToolTip(index, f'{pair[0]}\n{pair[1]}')
            except (OSError, ValueError) as error:
                msgInfo('無法開啟比較', str(error), self)
        if self.isMinimized():
            self.setWindowState(self.windowState() & ~Qt.WindowMinimized)
        self.show()
        self.raise_()
        self.activateWindow()

    def add_comparison_tab(self, window, pair):
        existing = next((page for page in self.windows if page.file_pair == pair), None)
        if existing is not None:
            if existing is not window: window.deleteLater()
            self.tabs.setCurrentWidget(existing)
            return
        super().add_comparison_tab(window, pair)
        self.update_watches()
        for session in self.folder_sessions:
            if session is not self: window.saved.connect(session.request_refresh)

    def publish_hex_result(self, window):
        for session in self.folder_sessions:
            ComparisonSession.publish_hex_result(session, window)

    def close_tab(self, index):
        page = self.tabs.widget(index)
        if isinstance(page, ComparisonSession):
            if page.busy or not page.close(): return
            self.tabs.removeTab(index)
            self.folder_sessions.remove(page)
            page.deleteLater()
            self.update_current_tab()
            return
        super().close_tab(index)
        if page is self.folder_tab: self.update_watches()

    def closeEvent(self, event):
        if any(session.busy for session in self.folder_sessions):
            msgInfo('工作進行中', '請等待目前工作完成後再關閉。', self)
            event.ignore()
            return
        super().closeEvent(event)
        if event.isAccepted():
            for session in self.folder_sessions:
                if session is not self: session.close()
