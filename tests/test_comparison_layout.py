import os
import pytest
from PySide6.QtCore import Qt
from lib.ui.main_window import MainWindow
from lib.ui.text_compare import TextCompare


def test_main_toolbar_has_short_captions_below_icons_without_tooltips(qtbot):
    from PySide6.QtWidgets import QToolButton
    window = MainWindow(); qtbot.addWidget(window)
    buttons = [button for button in window.tabs.widget(0).findChildren(QToolButton)
               if button.toolButtonStyle() == Qt.ToolButtonTextUnderIcon]
    assert len(buttons) == 14
    assert {button.text() for button in buttons} >= {'全部', '差異', '相同', '詳細比較', '交換左右'}
    assert all(not button.toolTip() for button in buttons)
    assert all(button.width() >= button.fontMetrics().horizontalAdvance(button.text()) + 8 for button in buttons)
    assert all(button.toolButtonStyle() == Qt.ToolButtonIconOnly for button in window.up_buttons)
    assert window.up_both_button.toolTip()
    window.close()


@pytest.mark.parametrize('first_is_folder', [True, False], ids=['folder-first', 'file-first'])
def test_cli_folder_pair_stays_on_folder_list(qtbot, tmp_path, monkeypatch, first_is_folder):
    import lib.ui.main_window as main
    left, right = tmp_path / 'left', tmp_path / 'right'
    for root in (left, right):
        root.mkdir()
        if first_is_folder:
            (root / 'sub').mkdir()
        else:
            (root / 'first.txt').write_bytes(b'contents')
    messages = []
    monkeypatch.setattr(main, 'msgInfo', lambda *args: messages.append(args[:2]))
    window = MainWindow(); qtbot.addWidget(window)
    window.auto_open_files = True
    window.left_path.setText(str(left)); window.right_path.setText(str(right))
    window.compare()
    qtbot.waitUntil(lambda: not window.busy, timeout=10000)
    qtbot.wait(50)
    assert window.tree.topLevelItemCount() == 1
    assert messages == []
    assert window.tabs.count() == 1
    window.close()


def test_paired_trees_expand_and_select_together(qtbot, tmp_path):
    left, right = tmp_path / 'l', tmp_path / 'r'
    for root in (left, right):
        (root / 'sub').mkdir(parents=True)
        (root / 'sub' / 'x.txt').write_bytes(b'same')
    window = MainWindow(); qtbot.addWidget(window)
    window.left_path.setText(str(left)); window.right_path.setText(str(right))
    window.compare()
    qtbot.waitUntil(lambda: not window.busy, timeout=10000)
    litem = window.tree.topLevelItem(0)
    ritem = window.right_tree.topLevelItem(0)
    assert litem.text(0) == ritem.text(0) == 'sub'
    assert litem.child(0).text(0) == ritem.child(0).text(0) == 'x.txt'
    window.tree.expandItem(litem)
    assert ritem.isExpanded()
    window.right_tree.setCurrentItem(ritem.child(0))
    assert window.selected()[0].relative == 'sub/x.txt'
    window.open_selected(); qtbot.waitUntil(lambda: not window.busy)
    assert isinstance(window.tabs.currentWidget(), TextCompare)
    assert not window.tabs.currentWidget().isWindow()
    window.close()


def test_copy_from_gutter_uses_current_block(qtbot, tmp_path):
    left, right = tmp_path / 'l', tmp_path / 'r'
    left.write_bytes(b'first\nnew\nlast\n')
    right.write_bytes(b'first\nold\nlast\n')
    window = TextCompare(left, right); qtbot.addWidget(window); window.show()
    window.left_edit.copy_at_line(1)
    window.save_side(1)
    assert right.read_bytes() == left.read_bytes()
    window.close()


def test_block_undo_redo_preserves_text_and_disk(qtbot, tmp_path):
    left, right = tmp_path / 'l', tmp_path / 'r'
    left.write_text('a\u00a0b\nnew\n', encoding='utf-8')
    right.write_text('a\u00a0b\nold\n', encoding='utf-8')
    window = TextCompare(left, right); qtbot.addWidget(window)
    assert callable(getattr(window, 'undo', None))
    window.copy_block('right')
    window.undo()
    assert window.texts[1] == 'a\u00a0b\nold\n'
    assert window.dirty == [False, False]
    window.redo()
    assert right.read_text(encoding='utf-8') == 'a\u00a0b\nold\n'
    window.save_side(1)
    assert right.read_text(encoding='utf-8') == 'a\u00a0b\nnew\n'
    window.close()


def test_find_text_selects_match_without_modifying_file(qtbot, tmp_path):
    left, right = tmp_path / 'l', tmp_path / 'r'
    for path in (left, right): path.write_bytes(b'one\nneedle\nlast\n')
    window = TextCompare(left, right); qtbot.addWidget(window)
    window.find_box.setText('needle')
    window.find_next()
    assert window.left_edit.textCursor().selectedText() == 'needle'
    assert window.dirty == [False, False]
    window.close()


def test_all_button_restores_black_identical_files(qtbot, tmp_path):
    left, right = tmp_path / 'l', tmp_path / 'r'
    left.mkdir(); right.mkdir()
    for path in (left / 'same.txt', right / 'same.txt'): path.write_bytes(b'same')
    stamp = (left / 'same.txt').stat()
    os.utime(right / 'same.txt', ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    (left / 'only.txt').write_bytes(b'only')
    window = MainWindow(); qtbot.addWidget(window)
    window.left_path.setText(str(left)); window.right_path.setText(str(right))
    window.compare(); qtbot.waitUntil(lambda: not window.busy, timeout=10000)
    window.diff_button.click()
    assert window.tree.topLevelItemCount() == 1
    window.all_button.click()
    assert window.tree.topLevelItemCount() == 2
    item = window.item_pairs['same.txt'][0]
    assert item.foreground(0).color().name() == '#000000'
    window.close()


def test_multiple_folder_copy_has_small_confirmation(qtbot, tmp_path):
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication, QMessageBox, QPushButton, QPlainTextEdit
    left, right = tmp_path / 'l', tmp_path / 'r'
    left.mkdir(); right.mkdir()
    for name in ('one', 'two'):
        (left / name).mkdir()
        (left / name / 'file.txt').write_bytes(name.encode())
    window = MainWindow(); qtbot.addWidget(window)
    window.left_path.setText(str(left)); window.right_path.setText(str(right))
    window.compare(); qtbot.waitUntil(lambda: not window.busy, timeout=10000)
    window.tree.topLevelItem(0).setSelected(True)
    window.tree.topLevelItem(1).setSelected(True)
    window.tree.topLevelItem(0).setExpanded(True)
    confirmed = []
    timer = QTimer()
    def accept():
        dialog = QApplication.activeModalWidget()
        if isinstance(dialog, QMessageBox) and dialog.windowTitle() == '確認覆寫與同步':
            confirmed.append(not dialog.findChildren(QPlainTextEdit))
            for button in dialog.findChildren(QPushButton):
                if button.text() == '確認執行': button.click(); timer.stop(); break
    timer.timeout.connect(accept); timer.start(20)
    window.prepare_copy(True)
    qtbot.waitUntil(lambda: (right / 'two' / 'file.txt').exists() and not window.busy and not window._refresh_pending, timeout=10000)
    timer.stop()
    assert confirmed == [True]
    assert (left / 'one' / 'file.txt').read_bytes() == (right / 'one' / 'file.txt').read_bytes()
    assert (left / 'two' / 'file.txt').read_bytes() == (right / 'two' / 'file.txt').read_bytes()
    assert window.tree.topLevelItemCount() == 2
    assert window.right_tree.topLevelItemCount() == 2
    assert all(row.status == 'same' for row in window.rows)
    assert window.item_pairs['one'][0].isExpanded()
    assert {row.relative for row in window.selected()} == {'one', 'two'}
    window.close()


def test_cli_file_pair_opens_text_tab_directly(qtbot, tmp_path):
    left, right = tmp_path / 'first.txt', tmp_path / 'second.txt'
    left.write_bytes(b'first'); right.write_bytes(b'second')
    window = MainWindow(); qtbot.addWidget(window)
    window.auto_open_files = True
    window.left_path.setText(str(left)); window.right_path.setText(str(right))
    window.compare()
    qtbot.waitUntil(lambda: not window.busy and window.tabs.count() == 2, timeout=10000)
    assert isinstance(window.tabs.currentWidget(), TextCompare)
    assert window.tabs.currentWidget().texts == ['first', 'second']
    window.close()


def test_external_file_change_refreshes_comparison(qtbot, tmp_path):
    left, right = tmp_path / 'l', tmp_path / 'r'
    left.mkdir(); right.mkdir()
    for path in (left / 'x.txt', right / 'x.txt'): path.write_bytes(b'same')
    window = MainWindow(); qtbot.addWidget(window)
    window.left_path.setText(str(left)); window.right_path.setText(str(right))
    window.compare(); qtbot.waitUntil(lambda: not window.busy, timeout=10000)
    (right / 'x.txt').write_bytes(b'changed')
    qtbot.waitUntil(lambda: any(row.status == 'different' for row in window.rows) and not window.busy, timeout=10000)
    assert window.tree.topLevelItemCount() == 1
    window.close()


def test_text_save_refreshes_folder_comparison(qtbot, tmp_path):
    left, right = tmp_path / 'l', tmp_path / 'r'
    left.mkdir(); right.mkdir()
    (left / 'x.txt').write_bytes(b'new content'); (right / 'x.txt').write_bytes(b'old')
    window = MainWindow(); qtbot.addWidget(window)
    window.left_path.setText(str(left)); window.right_path.setText(str(right))
    window.compare(); qtbot.waitUntil(lambda: not window.busy, timeout=10000)
    window.tree.setCurrentItem(window.tree.topLevelItem(0)); window.open_selected(); qtbot.waitUntil(lambda: not window.busy)
    text = window.tabs.currentWidget()
    text.copy_block('right'); text.save_side(1)
    qtbot.waitUntil(lambda: bool(window.rows) and window.rows[0].right_size == 11 and not window.busy and not window._refresh_pending, timeout=10000)
    assert window.tree.topLevelItemCount() == 1
    window.close()


def test_external_atomic_replacements_keep_watching(qtbot, tmp_path):
    left, right = tmp_path / 'l', tmp_path / 'r'
    left.mkdir(); right.mkdir()
    for path in (left / 'x.txt', right / 'x.txt'): path.write_bytes(b'same')
    stamp = (left / 'x.txt').stat()
    os.utime(right / 'x.txt', ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    window = MainWindow(); qtbot.addWidget(window)
    window.left_path.setText(str(left)); window.right_path.setText(str(right))
    window.compare(); qtbot.waitUntil(lambda: not window.busy, timeout=10000)
    for value, expected in ((b'changed', 'different'), (b'same', 'same')):
        temporary = right / 'replacement.tmp'; temporary.write_bytes(value)
        os.utime(temporary, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
        temporary.replace(right / 'x.txt')
        qtbot.waitUntil(lambda: any(row.relative == 'x.txt' and row.status == expected for row in window.rows) and not window.busy, timeout=10000)
    window.close()


def test_external_change_updates_clean_text_tab(qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr('lib.ui.external_reload.confirmBox', lambda *a, **k: True)
    left, right = tmp_path / 'l', tmp_path / 'r'
    left.mkdir(); right.mkdir()
    for path in (left / 'x.txt', right / 'x.txt'): path.write_bytes(b'old')
    window = MainWindow(); qtbot.addWidget(window)
    window.left_path.setText(str(left)); window.right_path.setText(str(right))
    window.compare(); qtbot.waitUntil(lambda: not window.busy, timeout=10000)
    window.tree.setCurrentItem(window.tree.topLevelItem(0)); window.open_selected(); qtbot.waitUntil(lambda: not window.busy)
    text = window.tabs.currentWidget()
    (right / 'x.txt').write_bytes(b'changed')
    window.external_reload.request()
    qtbot.waitUntil(lambda: text.texts[1] == 'changed' and not window.busy, timeout=10000)
    assert text.dirty == [False, False]
    window.close()


def test_external_change_preserves_unsaved_merge(qtbot, tmp_path):
    left, right = tmp_path / 'l', tmp_path / 'r'
    left.mkdir(); right.mkdir()
    (left / 'x.txt').write_bytes(b'new'); (right / 'x.txt').write_bytes(b'old')
    window = MainWindow(); qtbot.addWidget(window)
    window.left_path.setText(str(left)); window.right_path.setText(str(right))
    window.compare(); qtbot.waitUntil(lambda: not window.busy, timeout=10000)
    window.tree.setCurrentItem(window.tree.topLevelItem(0)); window.open_selected(); qtbot.waitUntil(lambda: not window.busy)
    text = window.tabs.currentWidget(); text.copy_block('right')
    (right / 'added.txt').write_bytes(b'external')
    qtbot.waitUntil(lambda: any(row.relative == 'added.txt' for row in window.rows) and not window.busy, timeout=10000)
    assert text.texts == ['new', 'new']
    assert text.dirty == [False, True]
    assert (right / 'x.txt').read_bytes() == b'old'
    text.undo()
    window.close()


def test_paths_compare_automatically_and_detect_changed_side(qtbot, tmp_path):
    left, right, replacement = [tmp_path / name for name in ('l', 'r', 'replacement')]
    for folder in (left, right, replacement): folder.mkdir()
    (left / 'first.txt').write_bytes(b'first')
    (replacement / 'second.txt').write_bytes(b'second')
    window = MainWindow(); qtbot.addWidget(window)
    window.left_path.setText(str(left))
    assert not window.busy
    assert window.compared_paths is None
    window.right_path.setText(str(right))
    qtbot.waitUntil(lambda: window.compared_paths == (str(left), str(right)) and not window.busy, timeout=10000)
    assert [row.relative for row in window.rows] == ['first.txt']
    window.left_path.setText(str(replacement))
    qtbot.waitUntil(lambda: window.compared_paths == (str(replacement), str(right)) and not window.busy, timeout=10000)
    assert [row.relative for row in window.rows] == ['second.txt']
    window.close()
