from PySide6.QtCore import QMimeData, QPoint, QPointF, Qt, QUrl
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QApplication
import pytest

from lib.ui.main_window import MainWindow


def drop(target, paths):
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(path)) for path in paths])
    point = target.rect().center()
    enter = QDragEnterEvent(point, Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier)
    QApplication.sendEvent(target, enter)
    event = QDropEvent(QPointF(point), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier)
    if enter.isAccepted(): QApplication.sendEvent(target, event)
    return enter.isAccepted() and event.isAccepted()


@pytest.fixture
def window(qtbot):
    window = MainWindow(); qtbot.addWidget(window)
    window.resize(1280, 750); window.show()
    yield window
    window.close()


def files(tmp_path, binary=False):
    paths = [tmp_path / name for name in ('left.txt', 'right.txt', 'other.txt')]
    for path in paths: path.write_bytes(b'\0' + path.name.encode() if binary else path.name.encode())
    return paths


def test_two_files_open_and_reuse_without_changing_dirty_page(window, qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr('lib.ui.text_compare.confirmBox', lambda *a, **k: True)
    paths = files(tmp_path)
    assert drop(window, paths[:2])
    qtbot.waitUntil(lambda: not window.busy)
    page = window.windows[0]
    page.commit_text(0, 'unsaved')
    assert drop(page.left_edit.viewport(), paths[:2])
    assert len(window.windows) == 1
    assert page.texts[0] == 'unsaved'
    assert drop(page.right_edit.viewport(), (paths[0], paths[2]))
    qtbot.waitUntil(lambda: not window.busy)
    assert len(window.windows) == 2
    assert page.texts[0] == 'unsaved'


@pytest.mark.parametrize('binary', [False, True], ids=['text', 'hex'])
@pytest.mark.parametrize('side', [0, 1])
def test_single_file_replaces_only_drop_side(window, qtbot, tmp_path, binary, side):
    paths = files(tmp_path, binary)
    window.open_file_pair(paths[:2]); qtbot.waitUntil(lambda: not window.busy)
    page = window.windows[0]
    views = page.views if binary else (page.left_edit, page.right_edit)
    assert drop(views[side].viewport(), paths[2:])
    qtbot.waitUntil(lambda: not window.busy)
    pair = list(paths[:2]); pair[side] = paths[2]
    assert window.windows[0].file_pair == tuple(pair)
    assert len(window.windows) == 1


def test_cancel_replacement_keeps_unsaved_content(window, qtbot, tmp_path, monkeypatch):
    paths = files(tmp_path)
    window.open_file_pair(paths[:2]); qtbot.waitUntil(lambda: not window.busy)
    page = window.windows[0]; page.commit_text(0, 'unsaved')
    monkeypatch.setattr('lib.ui.text_compare.confirmBox', lambda *a, **k: False)
    assert drop(page.left_edit.viewport(), paths[2:])
    qtbot.waitUntil(lambda: not window.busy)
    assert window.windows == [page]
    assert page.texts[0] == 'unsaved'
    assert page.file_pair == tuple(paths[:2])
    monkeypatch.setattr('lib.ui.text_compare.confirmBox', lambda *a, **k: True)


def test_invalid_drop_and_single_file_on_toolbar_do_nothing(window, qtbot, tmp_path):
    paths = files(tmp_path)
    assert not drop(window, paths[:1])
    assert not drop(window, paths)
    assert not drop(window.left_path, [tmp_path, paths[0]])
    assert not drop(window.left_path, [paths[0], tmp_path / 'missing'])
    assert not window.left_path.text()
    assert not window.windows
