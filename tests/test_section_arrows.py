import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor
from text_compare import TextCompare


@pytest.mark.parametrize('side', [0, 1], ids=['copy-right', 'copy-left'])
def test_visible_section_arrow_has_full_size_and_wide_click_target(qtbot, tmp_path, monkeypatch, side):
    import text_compare
    monkeypatch.setattr(text_compare, 'confirmBox', lambda *args, **kwargs: True)
    left, right = tmp_path / 'left.txt', tmp_path / 'right.txt'
    left.write_bytes(b'head\nleft\ntail\n')
    right.write_bytes(b'head\nright\ntail\n')
    window = TextCompare(left, right); qtbot.addWidget(window)
    window.show(); qtbot.waitExposed(window)
    editor = (window.left_edit, window.right_edit)[side]
    block = editor.document().findBlockByNumber(1)
    top = round(editor.blockBoundingGeometry(block).translated(editor.contentOffset()).top())
    height = round(editor.blockBoundingRect(block).height())
    image = editor.numbers.grab().toImage()
    gold = [(x, y) for x in range(min(24, image.width()))
            for y in range(top, min(top + height, image.height()))
            if image.pixelColor(x, y) == QColor('#ffdb85')]
    assert gold
    assert max(x for x, y in gold) - min(x for x, y in gold) >= 9
    # The number area must not merge; the full 24px arrow lane must merge.
    before = list(window.texts)
    qtbot.mouseClick(editor.numbers, Qt.LeftButton, pos=QPoint(27, top + height // 2))
    assert window.texts == before
    qtbot.mouseClick(editor.numbers, Qt.LeftButton, pos=QPoint(22, top + height // 2))
    assert window.texts == [before[side], before[side]]
    assert left.read_bytes() == b'head\nleft\ntail\n'
    assert right.read_bytes() == b'head\nright\ntail\n'
    window.texts = [doc.text for doc in window.docs]
    window.close()


def test_each_multiline_difference_has_a_bracket_to_its_last_row(qtbot, tmp_path):
    left, right = tmp_path / 'left.txt', tmp_path / 'right.txt'
    left.write_bytes(b'head\nA\nB\nsame\nC\nD\ntail\n')
    right.write_bytes(b'head\nx\ny\nsame\nz\nw\ntail\n')
    window = TextCompare(left, right); qtbot.addWidget(window)
    window.show(); qtbot.waitExposed(window)
    assert len(window.display_blocks) == 2
    for editor in (window.left_edit, window.right_edit):
        image = editor.numbers.grab().toImage()
        for start, end in window.display_blocks:
            last = editor.document().findBlockByNumber(end - 1)
            bottom = round(editor.blockBoundingGeometry(last).translated(editor.contentOffset()).bottom()) - 3
            assert all(image.pixelColor(x, bottom) == QColor('#777777') for x in range(12, 17))
    window.close()
