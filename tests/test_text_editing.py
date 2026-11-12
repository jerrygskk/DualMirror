import codecs
import pytest
from PySide6.QtCore import Qt, QMimeData
from PySide6.QtGui import QTextCursor, QInputMethodEvent
from text_compare import TextCompare


@pytest.fixture
def comparison(qtbot, tmp_path, monkeypatch):
    import text_compare
    monkeypatch.setattr(text_compare, 'confirmBox', lambda *a, **k: True)
    monkeypatch.setattr(text_compare, 'msgCritical', lambda *a, **k: None)
    left, right = tmp_path / 'left.txt', tmp_path / 'right.txt'
    left.write_bytes('a\u00a0😀\r\nextra\r\nlast\n'.encode('utf-8'))
    right.write_bytes('a\u00a0😀\r\nlast\n'.encode('utf-8'))
    window = TextCompare(left, right)
    qtbot.addWidget(window)
    window.show()
    yield window
    window.close()


def select_rows(editor, first, end):
    cursor = QTextCursor(editor.document().findBlockByNumber(first))
    block = editor.document().findBlockByNumber(end)
    cursor.setPosition(block.position() if block.isValid() else editor.document().characterCount() - 1,
                       QTextCursor.KeepAnchor)
    editor.setTextCursor(cursor)


@pytest.mark.parametrize('value', ['1', '中', '😀'], ids=['digit', 'cjk', 'non-bmp'])
def test_ime_preedit_after_eof_insert_never_commits_alignment_newline(qtbot, tmp_path, monkeypatch, value):
    from PySide6.QtWidgets import QApplication
    import text_compare
    monkeypatch.setattr(text_compare, 'confirmBox', lambda *a, **k: True)
    left, right = tmp_path / 'left', tmp_path / 'right'
    for path in (left, right): path.write_bytes(b'last\r\n')
    window = TextCompare(left, right); qtbot.addWidget(window)
    window.show()
    editor = window.left_edit
    editor.setFocus(); editor.moveCursor(QTextCursor.End)
    for count in (1, 2, 3):
        before = window.texts[0]
        QApplication.sendEvent(editor, QInputMethodEvent(value, []))
        QApplication.processEvents()
        assert window.texts[0] == before
        event = QInputMethodEvent(); event.setCommitString(value)
        QApplication.sendEvent(editor, event)
        QApplication.processEvents()
        assert window.texts[0] == 'last\n' + value * count
        assert editor.textCursor().blockNumber() == 1
    window.save_side(0)
    assert left.read_bytes() == b'last\r\n' + (value * 3).encode('utf-8')
    assert right.read_bytes() == b'last\r\n'
    window.close()


def test_typing_on_aligned_row_preserves_unicode_and_mixed_newlines(comparison, qtbot):
    w = comparison
    e = w.right_edit
    e.setTextCursor(QTextCursor(e.document().findBlockByNumber(2)))
    qtbot.keyClicks(e, 'new ')
    qtbot.waitUntil(lambda: w.texts[1] == 'a\u00a0😀\nnew last\n')
    w.save_side(1)
    assert w.file_paths[1].read_bytes() == 'a\u00a0😀\r\nnew last\r\n'.encode('utf-8')
    w.undo()
    assert w.texts[1] == 'a\u00a0😀\nnewlast\n'
    w.redo()
    assert w.texts[1] == 'a\u00a0😀\nnew last\n'


@pytest.mark.parametrize('ime', [False, True], ids=['keyboard', 'ime'])
def test_insert_between_repeated_characters_keeps_caret_at_insertion(qtbot, tmp_path, monkeypatch, ime):
    from PySide6.QtWidgets import QApplication
    import text_compare
    monkeypatch.setattr(text_compare, 'confirmBox', lambda *a, **k: True)
    paths = [tmp_path / 'left', tmp_path / 'right']
    for path in paths: path.write_bytes(b'1111\n')
    window = TextCompare(*paths); qtbot.addWidget(window)
    editor = window.left_edit
    cursor = editor.textCursor(); cursor.setPosition(1); editor.setTextCursor(cursor)
    if ime:
        event = QInputMethodEvent(); event.setCommitString('1')
        QApplication.sendEvent(editor, event)
    else:
        qtbot.keyClicks(editor, '1')
    window.flush_edit()
    assert window.texts[0] == '11111\n'
    assert editor.textCursor().position() == 2
    window.texts = [doc.text for doc in window.docs]
    window.close()


def test_ime_and_paste_keep_raw_characters(comparison, qtbot):
    w = comparison
    e = w.right_edit
    e.moveCursor(QTextCursor.End)
    event = QInputMethodEvent()
    event.setCommitString('中文')
    from PySide6.QtWidgets import QApplication
    QApplication.sendEvent(e, event)
    qtbot.waitUntil(lambda: w.texts[1].endswith('中文'))
    mime = QMimeData(); mime.setText('\u00a0😀\u2028x\u2029y\r\nz')
    e.insertFromMimeData(mime)
    assert w.texts[1].endswith('中文\u00a0😀\u2028x\u2029y\nz')
    w.save_side(1)
    assert '中文\u00a0😀\u2028x\u2029y\r\nz'.encode() in w.file_paths[1].read_bytes()


def test_selected_lines_merge_instead_of_whole_block(comparison):
    w = comparison
    w.texts = ['first\nA\nB\nlast\n', 'first\nX\nY\nlast\n']
    w.refresh()
    select_rows(w.left_edit, 1, 2)
    w.copy_block('right')
    assert w.texts[1] == 'first\nA\nY\nlast\n'
    w.undo()
    assert w.texts[1] == 'first\nX\nY\nlast\n'


def test_replace_all_is_one_undo_and_no_disk_write(comparison):
    w = comparison
    old = w.file_paths[1].read_bytes()
    w.active_side = 1
    w.find_box.setText('a')
    w.replace_box.setText('文字')
    w.replace_matches(True)
    assert w.texts[1] == '文字\u00a0😀\nl文字st\n'
    assert w.file_paths[1].read_bytes() == old
    w.undo()
    assert w.texts[1] == 'a\u00a0😀\nlast\n'


def test_save_as_keeps_original_files_and_encoding(comparison, tmp_path):
    w = comparison
    w.copy_block('right')
    before = [p.read_bytes() for p in w.file_paths]
    target = tmp_path / 'result.txt'
    assert w.save_as(1, target)
    assert target.read_bytes() == before[0]
    assert [p.read_bytes() for p in w.file_paths] == before
    assert w.dirty[1]
    assert not w.save_as(1, w.file_paths[0])


def test_save_as_preserves_utf16_big_endian(comparison, tmp_path):
    from core import TextFile
    w = comparison
    original = tmp_path / 'be.txt'
    original.write_bytes(codecs.BOM_UTF16_BE + '原文\r\n'.encode('utf-16-be'))
    w.docs[1] = TextFile.load(original)
    w.file_paths[1] = original
    w.texts[1] = '新文\n'
    target = tmp_path / 'new.txt'
    assert w.save_as(1, target)
    assert target.read_bytes() == codecs.BOM_UTF16_BE + '新文\r\n'.encode('utf-16-be')


def test_typing_on_placeholder_creates_real_line_without_copying_padding(comparison, qtbot):
    w = comparison
    e = w.right_edit
    e.setTextCursor(QTextCursor(e.document().findBlockByNumber(1)))
    qtbot.keyClicks(e, 'added')
    qtbot.waitUntil(lambda: w.texts[1] == 'a\u00a0😀\nadded\nlast\n')
    w.save_side(1)
    assert w.file_paths[1].read_bytes() == 'a\u00a0😀\r\nadded\r\nlast\n'.encode()


def test_deleting_padding_does_not_leave_untracked_display_change(comparison, qtbot):
    w = comparison
    e = w.right_edit
    e.setTextCursor(QTextCursor(e.document().findBlockByNumber(1)))
    qtbot.keyClick(e, Qt.Key_Delete)
    qtbot.waitUntil(lambda: e.line_numbers == [1, None, 2, 3] and e.blockCount() == 4)
    assert w.texts[1] == 'a\u00a0😀\nlast\n'
    assert not w.dirty[1]


def test_edit_then_merge_and_replace_share_history(comparison, qtbot):
    w = comparison
    e = w.right_edit
    e.moveCursor(QTextCursor.End)
    qtbot.keyClicks(e, 'z')
    qtbot.waitUntil(lambda: w.texts[1].endswith('z'))
    typed = w.texts[1]
    w.current = 0
    w.copy_block('right')
    merged = w.texts[1]
    w.active_side = 1
    w.find_box.setText('last'); w.replace_box.setText('end')
    w.replace_matches(True)
    w.undo(); assert w.texts[1] == merged
    w.undo(); assert w.texts[1] == typed
    w.undo(); assert w.texts[1] == 'a\u00a0😀\nlast\n'
    w.redo(); assert w.texts[1] == typed


def test_replace_current_only_changes_one_occurrence(comparison):
    w = comparison
    w.active_side = 1
    w.find_box.setText('a'); w.replace_box.setText('Q')
    w.place_cursor(1, 0)
    w.replace_matches()
    assert w.texts[1] == 'Q\u00a0😀\nlast\n'
    w.replace_matches()
    assert w.texts[1] == 'Q\u00a0😀\nlQst\n'


def test_save_as_rechecks_target_after_confirmation(comparison, tmp_path, monkeypatch):
    import text_compare
    target = tmp_path / 'existing.txt'
    target.write_bytes(b'old')
    def concurrent_change(*a, **k):
        target.write_bytes(b'external')
        return True
    monkeypatch.setattr(text_compare, 'confirmBox', concurrent_change)
    assert not comparison.save_as(1, target)
    assert target.read_bytes() == b'external'


def test_save_as_encoding_failure_keeps_target(comparison, tmp_path):
    from core import TextFile
    w = comparison
    original = tmp_path / 'big5.txt'
    original.write_bytes('原文'.encode('cp950'))
    w.docs[1] = TextFile.load(original); w.file_paths[1] = original
    w.texts[1] = '😀'
    target = tmp_path / 'existing.txt'; target.write_bytes(b'keep')
    assert not w.save_as(1, target)
    assert target.read_bytes() == b'keep'
    assert original.read_bytes() == '原文'.encode('cp950')


def test_external_change_blocks_saving_direct_edits(comparison, qtbot):
    w = comparison
    qtbot.keyClicks(w.right_edit, 'z')
    w.file_paths[1].write_bytes(b'external')
    w.save_side(1)
    assert w.file_paths[1].read_bytes() == b'external'


def test_missing_side_cannot_be_edited_or_saved(qtbot, tmp_path):
    existing, missing = tmp_path / 'exists', tmp_path / 'missing'
    existing.write_bytes(b'one')
    w = TextCompare(existing, missing); qtbot.addWidget(w)
    w.replace_selection(1, 'bad')
    w.active_side = 1
    w.find_box.setText('one'); w.replace_box.setText('bad')
    w.replace_matches(True)
    assert not w.save_as(1, tmp_path / 'output')
    assert not missing.exists()
    assert w.texts == ['one', '']
    w.close()


def test_main_window_edit_merge_replace_save_workflow(qtbot, tmp_path, monkeypatch):
    from main import MainWindow
    import text_compare
    monkeypatch.setattr(text_compare, 'confirmBox', lambda *a, **k: True)
    left, right = tmp_path / 'l.txt', tmp_path / 'r.txt'
    left.write_bytes(b'head\r\nnew\r\ntail\r\n')
    right.write_bytes(b'head\r\nold\r\ntail\r\n')
    main = MainWindow(); qtbot.addWidget(main)
    main.resize(1280, 750); main.show()
    main.auto_open_files = True
    main.left_path.setText(str(left)); main.right_path.setText(str(right))
    main.compare()
    qtbot.waitUntil(lambda: not main.busy and main.tabs.count() == 2)
    w = main.tabs.currentWidget()
    e = w.right_edit
    e.setFocus(); e.moveCursor(QTextCursor.End)
    qtbot.keyClicks(e, 'append')
    w.flush_edit()
    w.left_edit.setFocus()
    w.left_edit.setTextCursor(QTextCursor(w.left_edit.document().findBlockByNumber(1)))
    qtbot.mouseClick(w.to_right, Qt.LeftButton)
    e.setFocus()
    qtbot.keyClick(e, Qt.Key_H, Qt.ControlModifier)
    assert w.replace_panel.isVisible()
    w.find_box.setText('tail'); w.replace_box.setText('end')
    w.replace_matches(True)
    e.setFocus()
    qtbot.keyClick(e, Qt.Key_S, Qt.ControlModifier)
    qtbot.waitUntil(lambda: not w.dirty[1] and not main.busy)
    assert right.read_bytes() == b'head\r\nnew\r\nend\r\nappend'
    target = tmp_path / 'export.txt'
    assert w.save_as(1, target)
    assert target.read_bytes() == right.read_bytes()
    assert left.read_bytes() == b'head\r\nnew\r\ntail\r\n'
    main.close()
