from pathlib import Path

import pytest
from PySide6.QtCore import QPoint, Qt
from lib.ui.main_window import MainWindow


@pytest.mark.parametrize('sides', [(0,), (1,), (0, 1)], ids=['left', 'right', 'both'])
def test_up_buttons_change_only_requested_roots_and_compare(qtbot, tmp_path, sides):
    paths = [tmp_path / side / 'child' for side in ('left', 'right')]
    for path in paths:
        path.mkdir(parents=True)
        (path / 'sample.txt').write_bytes(b'same')
    window = MainWindow(); qtbot.addWidget(window); window.show()
    window.left_path.setText(str(paths[0])); window.right_path.setText(str(paths[1]))
    window.compare(); qtbot.waitUntil(lambda: not window.busy)
    button = window.up_both_button if len(sides) == 2 else window.up_buttons[sides[0]]
    qtbot.mouseClick(button, Qt.LeftButton)
    expected = tuple(str(path.parent if index in sides else path) for index, path in enumerate(paths))
    qtbot.waitUntil(lambda: window.compared_paths == expected and not window.busy, timeout=10000)
    assert window.paths() == expected
    assert all((path / 'sample.txt').read_bytes() == b'same' for path in paths)
    window.close()


def test_both_up_at_root_cannot_move_just_one_side(qtbot, tmp_path):
    window = MainWindow(); qtbot.addWidget(window)
    window.left_path.setText(Path(tmp_path.anchor).as_posix())
    window.right_path.setText(str(tmp_path))
    window.refresh_timer.stop()
    assert not window.up_buttons[0].isEnabled()
    assert window.up_buttons[1].isEnabled()
    assert not window.up_both_button.isEnabled()
    before = window.paths()
    window.navigate_up((0, 1))
    assert window.paths() == before
    window.close()


def test_navigation_rechecks_busy_and_missing_paths(qtbot, tmp_path):
    window = MainWindow(); qtbot.addWidget(window)
    window.left_path.setText(str(tmp_path))
    window.refresh_timer.stop()
    before = window.paths()
    window.busy = True
    window.navigate_up((0,))
    assert window.paths() == before
    window.busy = False
    window.left_path.setText(str(tmp_path / 'missing'))
    assert not window.up_buttons[0].isEnabled()
    before = window.paths()
    window.navigate_up((0,))
    assert window.paths() == before
    window.close()


def test_both_up_is_at_path_row_center_above_result_gutter(qtbot):
    window = MainWindow(); qtbot.addWidget(window)
    window.resize(1280, 750); window.show(); qtbot.waitExposed(window)
    button = window.up_both_button
    center = button.mapTo(window, button.rect().center())
    gutter = window.result_gutter
    assert abs(center.x() - gutter.mapTo(window, gutter.rect().center()).x()) <= 1
    assert center.y() < window.tree.header().mapTo(window, QPoint(0, 0)).y()
    assert button.parentWidget().parentWidget() is gutter
    assert button.toolButtonStyle() == Qt.ToolButtonIconOnly
    window.close()


def test_disabled_center_button_cannot_start_splitter_drag(qtbot):
    window = MainWindow(); qtbot.addWidget(window)
    window.resize(1280, 750); window.show(); qtbot.waitExposed(window)
    gutter = window.result_gutter
    area = window.gutter_button_area
    before = gutter.splitter().sizes()
    assert not window.up_both_button.isEnabled()
    assert area.cursor().shape() == Qt.ArrowCursor
    qtbot.mousePress(area, Qt.LeftButton, pos=QPoint(12, 10))
    qtbot.mouseMove(area, QPoint(112, 10))
    qtbot.mouseRelease(area, Qt.LeftButton, pos=QPoint(112, 10))
    assert gutter.splitter().sizes() == before
    qtbot.mouseMove(gutter, QPoint(12, 100))
    assert gutter.cursor().shape() == Qt.SplitHCursor
    window.close()
