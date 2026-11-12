from PySide6.QtCore import Qt
from lib.ui.main_window import MainWindow


def load_pair(window, qtbot, tmp_path):
    left, right = tmp_path / 'left', tmp_path / 'right'
    left.mkdir(parents=True); right.mkdir(parents=True)
    (left / 'one.txt').write_bytes(b'left\n')
    (right / 'one.txt').write_bytes(b'right\n')
    window.left_path.setText(str(left)); window.right_path.setText(str(right))
    window.compare(); qtbot.waitUntil(lambda: not window.busy)


def test_closing_folder_session_returns_home_and_can_start_again(qtbot, tmp_path):
    window = MainWindow(); qtbot.addWidget(window); window.show()
    load_pair(window, qtbot, tmp_path)
    window.close_tab(0)
    assert window.tabs.count() == 0
    assert window.isVisible()
    assert window.paths() == ('', '')
    assert not window.rows and not window.watcher.files() and not window.watcher.directories()
    assert not window.refresh_timer.isActive()
    assert window.home.isVisible()
    assert not window.close_tab_action.isEnabled()
    window.show_folder_tab()
    assert window.tabs.count() == 1
    assert window.tabs.currentWidget() is window.folder_tab
    load_pair(window, qtbot, tmp_path / 'again')
    assert len(window.rows) == 1
    window.close()


def test_text_tab_at_index_zero_still_closes_and_honors_unsaved_prompt(qtbot, tmp_path, monkeypatch):
    import lib.ui.text_compare as text_compare
    window = MainWindow(); qtbot.addWidget(window); window.show()
    load_pair(window, qtbot, tmp_path)
    window.tree.setCurrentItem(window.tree.topLevelItem(0)); window.open_selected()
    text = window.tabs.currentWidget()
    window.close_tab(0)
    assert window.tabs.currentWidget() is text and window.tabs.count() == 1
    text.commit_text(0, 'unsaved\n')
    monkeypatch.setattr(text_compare, 'confirmBox', lambda *a, **k: False)
    window.close_tab(0)
    assert window.tabs.count() == 1
    monkeypatch.setattr(text_compare, 'confirmBox', lambda *a, **k: True)
    qtbot.keyClick(window, Qt.Key_W, Qt.ControlModifier)
    assert window.tabs.count() == 0
    assert not window.windows
    assert window.home.isVisible()
    window.close()
