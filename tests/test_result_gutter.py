from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QColor
from lib.core.core import compare_paths, verify_contents
from lib.ui.main_window import MainWindow
from PySide6.QtWidgets import QHeaderView


def setup_window(qtbot, tmp_path):
    left, right = tmp_path / 'l', tmp_path / 'r'
    for folder in (left, right):
        (folder / 'sub').mkdir(parents=True)
        for number in range(70):
            (folder / 'sub' / f'{number:03}.bin').write_bytes(b'\0same')
    (right / 'sub' / '001.bin').write_bytes(b'\0diff')
    w = MainWindow(); qtbot.addWidget(w)
    w.rows = verify_contents(compare_paths(left, right)); w.render()
    w.resize(1280, 750); w.show(); w.expand_all()
    return w


def test_results_are_between_trees_and_outside_their_columns(qtbot, tmp_path):
    w = setup_window(qtbot, tmp_path)
    assert w.tree.columnCount() == w.right_tree.columnCount() == 3
    gutter = w.result_gutter
    assert gutter.parentWidget() is w.tree.parentWidget().parentWidget()
    left_edge = w.tree.mapTo(w, QPoint(w.tree.width(), 0)).x()
    right_edge = w.right_tree.mapTo(w, QPoint(0, 0)).x()
    assert left_edge <= gutter.mapTo(w, QPoint(0, 0)).x() < right_edge
    results = {name: (rect, symbol, color) for name, rect, symbol, color in gutter.visible_results()}
    assert results['sub/000.bin'][1:] == ('=', '#000000')
    assert results['sub/001.bin'][1:] == ('≠', '#e00000')
    w.close()


def test_gutter_tracks_scroll_collapse_and_horizontal_resize(qtbot, tmp_path):
    w = setup_window(qtbot, tmp_path)
    gutter = w.result_gutter
    width = gutter.width()
    w.tree.verticalScrollBar().setValue(100)
    w.tree.header().setSectionResizeMode(0, QHeaderView.Interactive)
    w.tree.header().resizeSection(0, 1400)
    w.tree.parentWidget().parentWidget().setSizes([400, 850])
    qtbot.waitUntil(lambda: w.tree.horizontalScrollBar().maximum() > 0)
    w.tree.horizontalScrollBar().setValue(300)
    qtbot.waitUntil(lambda: w.tree.verticalScrollBar().value() == w.right_tree.verticalScrollBar().value())
    assert gutter.width() == width
    assert w.tree.horizontalScrollBar().value() > 0
    for name, rect, symbol, color in gutter.visible_results():
        item = w.item_pairs[name][0]
        actual = w.tree.visualItemRect(item)
        expected = w.tree.viewport().mapTo(w, actual.topLeft()).y() - gutter.mapTo(w, QPoint(0, 0)).y()
        assert rect.top() == expected
        assert rect.height() == actual.height()
    w.collapse_all()
    assert gutter.visible_results() == []
    w.close()


def test_selected_difference_keeps_red_glyph_on_separate_background(qtbot, tmp_path):
    w = setup_window(qtbot, tmp_path)
    item = w.item_pairs['sub/001.bin'][0]
    w.tree.setCurrentItem(item)
    gutter = w.result_gutter
    image = gutter.grab().toImage()
    rect = next(rect for name, rect, symbol, color in gutter.visible_results() if name == 'sub/001.bin')
    pixels = [image.pixelColor(x, y) for x in range(2, image.width() - 2)
              for y in range(max(0, rect.top()), min(image.height(), rect.bottom() + 1))]
    assert any(c.red() > c.green() + 60 and c.red() > c.blue() + 60 for c in pixels)
    w.close()
