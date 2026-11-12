from PySide6.QtCore import QEvent, QTimer
from PySide6.QtWidgets import QApplication, QMessageBox
import pytest

from lib.ui.main_window import MainWindow


@pytest.fixture
def opened(qtbot, tmp_path, monkeypatch):
    pair = (tmp_path / 'left', tmp_path / 'right')
    for path in pair: path.write_bytes(b'old')
    window = MainWindow(); qtbot.addWidget(window)
    window.open_file_pair(pair); qtbot.waitUntil(lambda: not window.busy)
    monkeypatch.setattr('lib.ui.text_compare.confirmBox', lambda *a, **k: True)
    yield window, pair, window.windows[0]
    window.close()


def activate(window, qtbot):
    QApplication.sendEvent(window, QEvent(QEvent.WindowActivate))
    qtbot.waitUntil(lambda: window.external_reload.idle and not window.busy)


def test_both_sides_prompt_in_order_and_decline_is_remembered(opened, qtbot, monkeypatch):
    window, pair, page = opened
    questions = []
    def answer(title, text, **kwargs):
        questions.append(text)
        return '左側' in text
    monkeypatch.setattr('lib.ui.external_reload.confirmBox', answer)
    pair[0].write_bytes(b'left new'); pair[1].write_bytes(b'right new')
    window.refresh_if_ready()
    qtbot.waitUntil(lambda: not window.busy)
    assert page.texts == ['old', 'old']
    activate(window, qtbot)
    assert len(questions) == 2 and '左側' in questions[0] and '右側' in questions[1]
    assert page.texts == ['left new', 'old']
    activate(window, qtbot)
    assert len(questions) == 2
    pair[1].write_bytes(b'another change')
    activate(window, qtbot)
    assert len(questions) == 3


def test_accept_one_side_keeps_other_dirty_text_and_undo(opened, qtbot, monkeypatch):
    window, pair, page = opened
    page.commit_text(1, 'unsaved right')
    monkeypatch.setattr('lib.ui.external_reload.confirmBox', lambda *a, **k: True)
    pair[0].write_bytes(b'new left')
    activate(window, qtbot)
    assert page.texts == ['new left', 'unsaved right']
    assert page.dirty == [False, True]
    page.undo()
    assert page.texts == ['new left', 'old']


def test_dirty_side_warning_and_cancel_keep_original(opened, qtbot, monkeypatch):
    window, pair, page = opened
    page.commit_text(0, 'unsaved')
    questions = []
    monkeypatch.setattr('lib.ui.external_reload.confirmBox', lambda title, text, **k: questions.append(text) or False)
    pair[0].write_bytes(b'external')
    activate(window, qtbot)
    assert '未儲存' in questions[0]
    assert page.texts == ['unsaved', 'old']
    assert page.disk_baseline == (b'old', b'old')


def test_accept_dirty_side_and_deleted_file(opened, qtbot, monkeypatch):
    window, pair, page = opened
    page.commit_text(0, 'unsaved')
    monkeypatch.setattr('lib.ui.external_reload.confirmBox', lambda *a, **k: True)
    pair[0].write_bytes(b'new'); pair[1].unlink()
    activate(window, qtbot)
    assert page.texts == ['new', '']
    assert page.disk_baseline == (b'new', None)
    assert not any(page.dirty)


def test_hex_reload_only_approved_side(qtbot, tmp_path, monkeypatch):
    pair = (tmp_path / 'left', tmp_path / 'right')
    for path in pair: path.write_bytes(b'\0old')
    window = MainWindow(); qtbot.addWidget(window)
    window.open_file_pair(pair); qtbot.waitUntil(lambda: not window.busy)
    monkeypatch.setattr('lib.ui.external_reload.confirmBox', lambda title, text, **k: '右側' in text)
    for path in pair: path.write_bytes(b'\0new')
    activate(window, qtbot)
    page = window.windows[0]
    assert page.documents == [b'\0old', b'\0new']
    assert page.stamp is None
    window.close()


def test_changes_during_confirmation_are_not_applied(opened, qtbot, monkeypatch):
    window, pair, page = opened
    errors = []
    monkeypatch.setattr('lib.ui.main_window.msgCritical', lambda *args: errors.append(args))
    def answer(*args, **kwargs):
        pair[0].write_bytes(b'changed again')
        return True
    monkeypatch.setattr('lib.ui.external_reload.confirmBox', answer)
    pair[0].write_bytes(b'changed')
    activate(window, qtbot)
    assert errors and page.texts == ['old', 'old']
    assert pair[0].read_bytes() == b'changed again'


def test_real_dialogs_update_left_then_right(opened, qtbot):
    window, pair, page = opened
    window.resize(1280, 750); window.show()
    qtbot.waitUntil(lambda: window.external_reload.idle and not window.busy)
    for path in pair: path.write_bytes(b'new')
    questions = []
    timer = QTimer(window)
    def approve():
        dialog = QApplication.activeModalWidget()
        if isinstance(dialog, QMessageBox) and dialog.windowTitle() == '檔案已變更':
            questions.append(dialog.text())
            next(button for button in dialog.buttons() if button.text() == '更新').click()
    timer.timeout.connect(approve); timer.start(20)
    try:
        activate(window, qtbot)
        assert page.texts == ['new', 'new']
        assert len(questions) == 2 and '左側' in questions[0] and '右側' in questions[1]
    finally:
        timer.stop()
