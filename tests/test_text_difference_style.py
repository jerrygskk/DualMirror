from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from text_compare import TextCompare


def test_insertions_use_hatched_gaps_and_red_text_separate_from_blank_rows(qtbot, tmp_path):
    left, right = tmp_path / 'left.txt', tmp_path / 'right.txt'
    common = 'repeated section\nfirst item\nsecond item\n'
    left.write_text('header\n\nextra\nextra\n\n' + common + '\n\n' + common, encoding='utf-8')
    right.write_text('header\n' + common, encoding='utf-8')
    window = TextCompare(left, right); qtbot.addWidget(window)
    assert len(window.blocks) == 2
    for editor in (window.left_edit, window.right_edit):
        for selection in editor.extraSelections():
            row = selection.cursor.blockNumber()
            if not any(start <= row < end for start, end in window.display_blocks): continue
            brush = selection.format.background()
            if row < len(editor.line_numbers) and editor.line_numbers[row] is None:
                assert brush.style() in (Qt.BDiagPattern, Qt.DiagCrossPattern)
            elif selection.cursor.block().text():
                color = brush.color()
                assert color.red() > color.green() and color.red() > color.blue()
                foreground = selection.format.foreground().color()
                assert foreground.red() > foreground.green() + 100
            else:
                color = brush.color()
                assert color.blue() > color.red()
    # Clicking a section still only transfers that section; display patterns
    # must never become part of either document's text.
    start = window.display_blocks[0][0]
    window.left_edit.setTextCursor(QTextCursor(window.left_edit.document().findBlockByNumber(start)))
    window.left_edit.copy_at_line(start)
    assert window.texts[1] == 'header\n\nextra\nextra\n\n' + common
    assert right.read_text(encoding='utf-8') == 'header\n' + common
    window.texts = [doc.text for doc in window.docs]
    window.close()


def test_hatched_gap_is_continuous_across_blank_row_boundaries(qtbot, tmp_path):
    from PySide6.QtGui import QFont
    left, right = tmp_path / 'left', tmp_path / 'right'
    left.write_text('中文\n新增\n新增\n新增\n結尾\n', encoding='utf-8')
    right.write_text('中文\n結尾\n', encoding='utf-8')
    window = TextCompare(left, right); qtbot.addWidget(window)
    for editor in (window.left_edit, window.right_edit): editor.setFont(QFont('Consolas', 10))
    window.show(); qtbot.waitExposed(window)
    editor = window.right_edit
    first = editor.document().findBlockByNumber(1)
    last = editor.document().findBlockByNumber(3)
    top = round(editor.blockBoundingGeometry(first).translated(editor.contentOffset()).top())
    bottom = round(editor.blockBoundingGeometry(last).translated(editor.contentOffset()).bottom())
    image = editor.viewport().grab().toImage()
    scale = image.devicePixelRatio()
    for y in range(round(top * scale), round(bottom * scale)):
        assert any(image.pixelColor(x, y).red() < 230 for x in range(round(80 * scale), round(240 * scale)))
    # Qt's built-in hatch tile repeats every eight device pixels.
    period = 8
    for y in range(round(top * scale), round(bottom * scale) - period):
        assert all(image.pixelColor(x, y) == image.pixelColor(x, y + period)
                   for x in range(round(80 * scale), round(240 * scale)))
    window.close()
