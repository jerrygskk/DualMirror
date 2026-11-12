from PySide6.QtGui import QFont
from PySide6.QtCore import QPoint, Qt
from core import differences
from text_compare import TextCompare
import pytest


def test_matching_text_is_not_displaced_by_long_blank_runs():
    left = 'top\n' + '\n' * 30 + 'anchor\n\nend\n'
    right = 'top\n\nanchor\n' + '\n' * 30 + 'end\n'
    ll, rr = left.splitlines(True), right.splitlines(True)
    for tag, a, b, c, d in differences(left, right):
        assert all(not line.strip() for line in ll[a:b] + rr[c:d])


@pytest.mark.parametrize('source', [0, 1], ids=['left-to-right', 'right-to-left'])
def test_merging_selected_line_does_not_recenter_view(qtbot, tmp_path, monkeypatch, source):
    import text_compare
    monkeypatch.setattr(text_compare, 'confirmBox', lambda *a, **k: True)
    paths = [tmp_path / 'left', tmp_path / 'right']
    head = ''.join(f'common {i}\n' for i in range(20))
    tail = ''.join(f'tail {i}\n' for i in range(30))
    paths[source].write_text(head + ''.join(f'extra {i}\n' for i in range(10)) + tail, encoding='utf-8')
    paths[1 - source].write_text(head + tail, encoding='utf-8')
    window = TextCompare(*paths); qtbot.addWidget(window)
    window.resize(1000, 450); window.show(); qtbot.waitExposed(window)
    editor = (window.left_edit, window.right_edit)[source]
    row = editor.line_numbers.index(25)
    editor.select_whole_rows(row, row)
    window.left_edit.verticalScrollBar().setValue(0)
    before = editor.blockBoundingGeometry(editor.document().findBlockByNumber(row)).translated(editor.contentOffset()).top()
    editor.copy_at_line(row)
    qtbot.wait(20)
    after_row = editor.line_numbers.index(25)
    after = editor.blockBoundingGeometry(editor.document().findBlockByNumber(after_row)).translated(editor.contentOffset()).top()
    assert after == before
    assert window.left_edit.verticalScrollBar().value() == window.right_edit.verticalScrollBar().value() == 0
    assert window.texts[1 - source] == head + 'extra 4\n' + tail
    window.texts = [doc.text for doc in window.docs]
    window.close()


def test_partial_merge_keeps_chinese_blank_and_placeholder_rows_at_same_y(qtbot, tmp_path, monkeypatch):
    import text_compare
    monkeypatch.setattr(text_compare, 'confirmBox', lambda *a, **k: True)
    left, right = tmp_path / 'left', tmp_path / 'right'
    head = ''.join(f'第{i}行 中文 sample\n' for i in range(1, 20))
    tail = '相同段落\n第一筆\n第二筆\n'
    left.write_text(head + tail, encoding='utf-8')
    right.write_text(head + '\n新增\n新增\n第二筆\n交易方式\n\n' + tail, encoding='utf-8')
    window = TextCompare(left, right); qtbot.addWidget(window)
    for editor in (window.left_edit, window.right_edit): editor.setFont(QFont('Consolas', 10))
    window.resize(900, 450); window.show(); qtbot.waitExposed(window)
    e = window.right_edit
    first, last = e.line_numbers.index(23), e.line_numbers.index(24)
    e.select_whole_rows(first, last); e.copy_at_line(first)
    qtbot.wait(30)
    assert window.left_edit.firstVisibleBlock().blockNumber() == window.right_edit.firstVisibleBlock().blockNumber()
    for row in range(window.left_edit.blockCount()):
        tops = [editor.blockBoundingGeometry(editor.document().findBlockByNumber(row)).translated(editor.contentOffset()).top()
                for editor in (window.left_edit, window.right_edit)]
        assert abs(tops[0] - tops[1]) < 1
    window.texts = [doc.text for doc in window.docs]
    window.close()


def test_right_empty_arrow_lane_can_drag_select_whole_equal_rows(qtbot, tmp_path):
    left, right = tmp_path / 'left', tmp_path / 'right'
    for path in (left, right): path.write_bytes(b'head\none\ntwo\ntail\n')
    window = TextCompare(left, right); qtbot.addWidget(window); window.show()
    qtbot.waitExposed(window)
    e = window.right_edit
    def point(row):
        rect = e.blockBoundingGeometry(e.document().findBlockByNumber(row)).translated(e.contentOffset())
        return QPoint(12, round(rect.center().y()))
    qtbot.mousePress(e.numbers, Qt.LeftButton, pos=point(1))
    qtbot.mouseMove(e.numbers, point(2))
    qtbot.mouseRelease(e.numbers, Qt.LeftButton, pos=point(2))
    assert e.textCursor().selectedText() == 'one\u2029two\u2029'
    assert window.custom_rows == (1, 1, 3)
    window.close()
