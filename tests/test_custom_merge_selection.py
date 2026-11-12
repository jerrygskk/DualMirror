import pytest
from PySide6.QtCore import QPoint, QPointF, Qt, QEvent
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication
from text_compare import TextCompare


def row_point(editor, row, x=28):
    block = editor.document().findBlockByNumber(row)
    rect = editor.blockBoundingGeometry(block).translated(editor.contentOffset())
    return QPoint(x, round(rect.center().y()))


@pytest.fixture
def custom_window(qtbot, tmp_path, monkeypatch):
    import text_compare
    monkeypatch.setattr(text_compare, 'confirmBox', lambda *a, **k: True)
    paths = [tmp_path / 'left.txt', tmp_path / 'right.txt']
    paths[0].write_bytes(b'head\nA\nB\nC\ntail\n')
    paths[1].write_bytes(b'head\nx\ny\nz\ntail\n')
    window = TextCompare(*paths); qtbot.addWidget(window); window.show()
    qtbot.waitExposed(window)
    yield window
    window.texts = [doc.text for doc in window.docs]
    window.close()


@pytest.mark.parametrize('side', [0, 1])
def test_clicking_text_creates_one_line_merge(custom_window, qtbot, side):
    w = custom_window
    editor = (w.left_edit, w.right_edit)[side]
    before = list(w.texts)
    qtbot.mouseClick(editor.viewport(), Qt.LeftButton, pos=row_point(editor, 2, 5))
    qtbot.mouseClick(editor.numbers, Qt.LeftButton, pos=row_point(editor, 2, 12))
    expected = 'head\nx\nB\nz\ntail\n' if side == 0 else 'head\nA\ny\nC\ntail\n'
    assert w.texts[1 - side] == expected
    assert w.texts[side] == before[side]
    assert w.file_paths[1 - side].read_text(encoding='utf-8') == before[1 - side]
    w.undo()
    assert w.texts == before


@pytest.mark.parametrize('first,last', [(1, 2), (2, 1)], ids=['down', 'up'])
def test_dragging_line_numbers_selects_complete_lines_and_merges(custom_window, qtbot, first, last):
    w = custom_window; e = w.left_edit
    qtbot.mousePress(e.numbers, Qt.LeftButton, pos=row_point(e, first))
    qtbot.mouseMove(e.numbers, row_point(e, last))
    qtbot.mouseRelease(e.numbers, Qt.LeftButton, pos=row_point(e, last))
    assert e.textCursor().selectedText() == 'A\u2029B\u2029'
    qtbot.mouseClick(e.numbers, Qt.LeftButton, pos=row_point(e, 1, 12))
    assert w.texts[1] == 'head\nA\nB\nz\ntail\n'


def test_dragging_text_updates_custom_rows_without_modifying_data(custom_window, qtbot):
    w = custom_window; e = w.left_edit
    qtbot.mousePress(e.viewport(), Qt.LeftButton, pos=row_point(e, 1, 5))
    point = row_point(e, 2, 20)
    QApplication.sendEvent(e.viewport(), QMouseEvent(QEvent.MouseMove, QPointF(point),
        QPointF(e.viewport().mapToGlobal(point)), Qt.NoButton, Qt.LeftButton, Qt.NoModifier))
    qtbot.mouseRelease(e.viewport(), Qt.LeftButton, pos=row_point(e, 2, 10))
    assert w.texts[1] == 'head\nx\ny\nz\ntail\n'
    qtbot.mouseClick(e.numbers, Qt.LeftButton, pos=row_point(e, 1, 12))
    assert w.texts[1] == 'head\nA\nB\nz\ntail\n'
