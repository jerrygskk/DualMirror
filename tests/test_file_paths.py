from pathlib import Path
from PySide6.QtCore import Qt
from main import MainWindow
from text_compare import TextCompare


def setup_pair(qtbot, tmp_path):
    paths = [tmp_path / name for name in ('left.txt', 'right.txt', 'other.txt')]
    for path, text in zip(paths, ('left\n', 'right\n', 'other\n')):
        path.write_text(text, encoding='utf-8')
    window = MainWindow(); qtbot.addWidget(window)
    window.open_startup_pair(paths[:2])
    return window, paths


def test_startup_and_enter_replace_only_requested_side(qtbot, tmp_path):
    window, paths = setup_pair(qtbot, tmp_path)
    assert window.tabs.count() == 1
    page = window.tabs.currentWidget()
    assert isinstance(page, TextCompare)
    assert not page.path_edits[0].isReadOnly()
    row = page.path_edits[0].parentWidget().layout().itemAt(0).layout()
    assert row.itemAt(1).widget() is page.path_edits[0]
    assert row.itemAt(2).widget() is page.save_left
    page.path_edits[1].setText(str(paths[2]))
    qtbot.keyClick(page.path_edits[1], Qt.Key_Return)
    current = window.tabs.currentWidget()
    assert window.tabs.count() == 1
    assert current.file_pair == (paths[0], paths[2])
    assert current.texts == ['left\n', 'other\n']
    assert str(paths[2]) in window.watcher.files()
    window.close()


def test_invalid_path_and_cancel_keep_dirty_content(qtbot, tmp_path, monkeypatch):
    import main
    import text_compare
    window, paths = setup_pair(qtbot, tmp_path)
    page = window.tabs.currentWidget()
    page.commit_text(0, 'unsaved\n')
    monkeypatch.setattr(main, 'msgInfo', lambda *args: None)
    window.replace_comparison_path(page, 0, str(tmp_path))
    assert window.tabs.currentWidget() is page
    monkeypatch.setattr(text_compare, 'confirmBox', lambda *args, **kwargs: False)
    page.path_edits[0].setText(str(paths[2]))
    page.request_path(0)
    assert window.tabs.currentWidget() is page
    assert page.texts[0] == 'unsaved\n'
    assert page.path_edits[0].text() == str(paths[0])
    assert paths[0].read_text(encoding='utf-8') == 'left\n'
    monkeypatch.setattr(text_compare, 'confirmBox', lambda *args, **kwargs: True)
    window.close()


def test_browse_and_reuse_existing_pair(qtbot, tmp_path, monkeypatch):
    import text_compare
    window, paths = setup_pair(qtbot, tmp_path)
    first = window.tabs.currentWidget()
    window.open_file_pair((paths[0], paths[2]))
    second = window.tabs.currentWidget()
    monkeypatch.setattr(text_compare.QFileDialog, 'getOpenFileName', lambda *args: (str(paths[2]), ''))
    first.browse_path(1)
    assert window.tabs.count() == 1
    assert window.tabs.currentWidget() is second
    paths[2].write_text('updated\n', encoding='utf-8')
    window.refresh_if_ready()
    qtbot.waitUntil(lambda: not window.busy)
    assert second.texts[1] == 'updated\n'
    window.close()
