import os
from PySide6.QtCore import Qt
from lib.ui.text_compare import TextCompare
from lib.ui.main_window import MainWindow
from PySide6.QtWidgets import QApplication, QDialog, QPushButton
from PySide6.QtCore import QTimer


def test_merge_and_save_real_files(qtbot, tmp_path):
    left, right = tmp_path / 'left.txt', tmp_path / 'right.txt'
    left.write_bytes(b'one\r\nnew\r\nthree\r\n')
    right.write_bytes(b'one\r\nold\r\nthree\r\n')
    window = TextCompare(left, right)
    qtbot.addWidget(window); window.show()
    qtbot.mouseClick(window.to_right, Qt.LeftButton)
    assert window.right_edit.toPlainText() == 'one\nnew\nthree\n'
    assert right.read_bytes() == b'one\r\nold\r\nthree\r\n'
    qtbot.mouseClick(window.save_right, Qt.LeftButton)
    assert right.read_bytes() == left.read_bytes()
    assert not window.blocks
    window.close()


def test_scan_folder_and_filter(qtbot, tmp_path):
    left, right = tmp_path / 'left', tmp_path / 'right'
    left.mkdir(); right.mkdir()
    for root in (left, right): (root / 'same.txt').write_bytes(b'same')
    stamp = (left / 'same.txt').stat()
    os.utime(right / 'same.txt', ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    (left / 'extra.txt').write_bytes(b'extra')
    window = MainWindow(); qtbot.addWidget(window); window.show()
    window.left_path.setText(str(left)); window.right_path.setText(str(right))
    qtbot.mouseClick(window.compare_button, Qt.LeftButton)
    qtbot.waitUntil(lambda: not window.busy, timeout=10000)
    assert window.tree.topLevelItemCount() == 2
    window.filter_box.setCurrentIndex(1)
    assert window.tree.topLevelItemCount() == 1
    assert window.tree.topLevelItem(0).text(0) == 'extra.txt'
    window.close()


def test_multiple_blocks_copy_selected(qtbot, tmp_path):
    left, right = tmp_path / 'l', tmp_path / 'r'
    left.write_text('a\nx\nc\nd\ne\nz\n', encoding='utf-8')
    right.write_text('a\ny\nc\nd\ne\nw\n', encoding='utf-8')
    window = TextCompare(left, right); qtbot.addWidget(window); window.show()
    qtbot.mouseClick(window.next, Qt.LeftButton)
    assert window.current == 1
    qtbot.mouseClick(window.to_right, Qt.LeftButton)
    assert window.right_edit.toPlainText() == 'a\ny\nc\nd\ne\nz\n'
    qtbot.mouseClick(window.save_right, Qt.LeftButton)
    window.close()


def test_real_sync_preview_and_execute(qtbot, tmp_path, monkeypatch):
    errors = []
    monkeypatch.setattr('lib.ui.main_window.msgCritical', lambda *args: errors.append(str(args)))
    left, right = tmp_path / 'l', tmp_path / 'r'
    left.mkdir(); right.mkdir()
    (left / 'x.bin').write_bytes(b'\x00new')
    (right / 'x.bin').write_bytes(b'\x00old')
    (right / 'keep.txt').write_bytes(b'keep')
    window = MainWindow(); qtbot.addWidget(window); window.show()
    window.left_path.setText(str(left)); window.right_path.setText(str(right))
    qtbot.mouseClick(window.compare_button, Qt.LeftButton)
    qtbot.waitUntil(lambda: not window.busy, timeout=10000)
    timer = QTimer()
    def approve():
        dialog = QApplication.activeModalWidget()
        if dialog and dialog.windowTitle() == '確認覆寫與同步':
            for button in dialog.findChildren(QPushButton):
                if button.text() == '確認執行':
                    button.click(); timer.stop(); break
    timer.timeout.connect(approve); timer.start(20)
    qtbot.mouseClick(window.sync_right, Qt.LeftButton)
    qtbot.waitUntil(lambda: not window.busy, timeout=10000)
    timer.stop()
    assert not errors, '\n'.join(errors)
    assert (right / 'x.bin').read_bytes() == b'\x00new'
    assert (right / 'keep.txt').read_bytes() == b'keep'
    window.close()


def test_public_theme_has_readable_editor_background(qtbot, tmp_path):
    from lib.ui.theme import APP_STYLE, apply_light_palette
    app = QApplication.instance()
    apply_light_palette(app); app.setStyleSheet(APP_STYLE)
    left, right = tmp_path / 'l', tmp_path / 'r'
    left.write_bytes(b'left'); right.write_bytes(b'right')
    window = TextCompare(left, right); qtbot.addWidget(window); window.show()
    qtbot.waitExposed(window)
    image = window.right_edit.viewport().grab().toImage()
    color = image.pixelColor(image.width() // 2, image.height() - 20)
    assert min(color.red(), color.green(), color.blue()) > 220
    window.close()


def test_merge_preserves_nonbreaking_space(qtbot, tmp_path, monkeypatch):
    import lib.ui.text_compare as text_compare
    monkeypatch.setattr(text_compare, 'confirmBox', lambda *args, **kwargs: True)
    left, right = tmp_path / 'l', tmp_path / 'r'
    left.write_text('a\u00a0b\nnew\n', encoding='utf-8')
    right.write_text('a\u00a0b\nold\n', encoding='utf-8')
    window = TextCompare(left, right); qtbot.addWidget(window)
    window.copy_block('right'); window.save_side(1)
    assert right.read_text(encoding='utf-8') == 'a\u00a0b\nnew\n'
    window.close()


def test_changed_source_blocks_text_merge(qtbot, tmp_path, monkeypatch):
    import lib.ui.text_compare as text_compare
    monkeypatch.setattr(text_compare, 'msgCritical', lambda *args: None)
    left, right = tmp_path / 'l', tmp_path / 'r'
    left.write_bytes(b'new'); right.write_bytes(b'old')
    window = TextCompare(left, right); qtbot.addWidget(window)
    left.write_bytes(b'external change')
    window.copy_block('right'); window.save_side(1)
    assert right.read_bytes() == b'old'
    window.close()


def test_inserted_lines_align_matching_content(qtbot, tmp_path):
    left, right = tmp_path / 'l', tmp_path / 'r'
    left.write_bytes(b'first\nextra\nlast\n')
    right.write_bytes(b'first\nlast\n')
    window = TextCompare(left, right); qtbot.addWidget(window)
    assert window.right_edit.toPlainText().split('\n')[2] == 'last'
    assert window.right_edit.line_numbers[:3] == [1, None, 2]
    window.copy_block('right'); window.save_side(1)
    assert right.read_bytes() == left.read_bytes()
    window.close()


def test_source_changed_after_merge_blocks_save(qtbot, tmp_path, monkeypatch):
    import lib.ui.text_compare as text_compare
    monkeypatch.setattr(text_compare, 'msgCritical', lambda *args: None)
    monkeypatch.setattr(text_compare, 'confirmBox', lambda *args, **kwargs: True)
    left, right = tmp_path / 'l', tmp_path / 'r'
    left.write_bytes(b'new'); right.write_bytes(b'old')
    window = TextCompare(left, right); qtbot.addWidget(window)
    window.copy_block('right')
    left.write_bytes(b'changed')
    window.save_side(1)
    assert right.read_bytes() == b'old'
    window.close()


def test_identical_unicode_files_open_clean(qtbot, tmp_path):
    left, right = tmp_path / 'l', tmp_path / 'r'
    for path in (left, right): path.write_text('a\u00a0b\u2028c\n', encoding='utf-8')
    window = TextCompare(left, right); qtbot.addWidget(window)
    assert window.dirty == [False, False]
    assert window.blocks == []
    window.close()


def test_file_comparison_opens_in_existing_window_tab(qtbot, tmp_path):
    from PySide6.QtWidgets import QTabWidget
    left, right = tmp_path / 'l', tmp_path / 'r'
    left.mkdir(); right.mkdir()
    (left / 'test.txt').write_bytes(b'new')
    (right / 'test.txt').write_bytes(b'old')
    window = MainWindow(); qtbot.addWidget(window); window.show()
    window.left_path.setText(str(left)); window.right_path.setText(str(right))
    window.compare()
    qtbot.waitUntil(lambda: not window.busy, timeout=10000)
    window.tree.setCurrentItem(window.tree.topLevelItem(0))
    window.open_selected(); qtbot.waitUntil(lambda: not window.busy)
    assert isinstance(window.tabs, QTabWidget)
    assert window.isAncestorOf(window.tabs) and window.tabs.isVisible()
    assert window.tabs.count() == 2
    assert isinstance(window.tabs.currentWidget(), TextCompare)
    assert not window.tabs.currentWidget().isWindow()
    window.open_selected(); qtbot.waitUntil(lambda: not window.busy)
    assert window.tabs.count() == 2
    window.close_tab(1)
    assert window.tabs.count() == 1
    window.close()


def test_one_sided_text_opens_with_missing_side_disabled(qtbot, tmp_path, monkeypatch):
    import lib.ui.main_window as main
    monkeypatch.setattr(main, 'msgInfo', lambda *args, **kwargs: None)
    left, right = tmp_path / 'l', tmp_path / 'r'
    left.mkdir(); right.mkdir()
    (left / 'only.txt').write_bytes(b'available')
    window = MainWindow(); qtbot.addWidget(window)
    window.left_path.setText(str(left)); window.right_path.setText(str(right))
    window.compare(); qtbot.waitUntil(lambda: not window.busy, timeout=10000)
    window.tree.setCurrentItem(window.tree.topLevelItem(0)); window.open_selected(); qtbot.waitUntil(lambda: not window.busy)
    assert window.tabs.count() == 2
    comparison = window.tabs.currentWidget()
    assert comparison.left_edit.toPlainText() == 'available'
    assert not comparison.right_edit.isEnabled()
    assert '檔案不存在' in comparison.labels[1].text()
    comparison.copy_block('right')
    comparison.copy_block('left')
    comparison.save_side(1)
    assert not (right / 'only.txt').exists()
    assert (left / 'only.txt').read_bytes() == b'available'
    assert comparison.dirty == [False, False]
    window.close()


def test_missing_left_is_disabled_and_cannot_overwrite_right(qtbot, tmp_path):
    left, right = tmp_path / 'absent.txt', tmp_path / 'existing.txt'
    right.write_bytes(b'keep')
    window = TextCompare(left, right); qtbot.addWidget(window)
    assert not window.left_edit.isEnabled()
    assert window.right_edit.isEnabled()
    window.copy_block('left'); window.copy_block('right'); window.save_side(0)
    assert not left.exists()
    assert right.read_bytes() == b'keep'
    assert window.texts == ['', 'keep']
    window.close()


def test_missing_side_becomes_available_after_file_created(qtbot, tmp_path):
    left, right = tmp_path / 'l', tmp_path / 'r'
    left.mkdir(); right.mkdir()
    (left / 'only.txt').write_bytes(b'left')
    window = MainWindow(); qtbot.addWidget(window)
    window.left_path.setText(str(left)); window.right_path.setText(str(right))
    window.compare(); qtbot.waitUntil(lambda: not window.busy, timeout=10000)
    window.tree.setCurrentItem(window.tree.topLevelItem(0)); window.open_selected(); qtbot.waitUntil(lambda: not window.busy)
    comparison = window.tabs.currentWidget()
    assert not comparison.right_edit.isEnabled()
    (right / 'only.txt').write_bytes(b'right')
    qtbot.waitUntil(lambda: comparison.right_edit.isEnabled() and not window.busy, timeout=10000)
    assert comparison.texts == ['left', 'right']
    (right / 'only.txt').unlink()
    qtbot.waitUntil(lambda: not comparison.right_edit.isEnabled() and not window.busy, timeout=10000)
    assert comparison.texts == ['left', '']
    window.close()
