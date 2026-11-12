from pathlib import Path
import pytest
from PySide6.QtWidgets import QMenu
import lib.ui.main_window as main
import lib.integration.shell_integration as shell_integration


def menu(window):
    return next(value for value in window.findChildren(QMenu) if value.title() == '整合')


def test_registration_and_removal_are_explicit_separate_actions(qtbot):
    window = main.MainWindow(); qtbot.addWidget(window)
    actions = menu(window).actions()
    assert [action.text() for action in actions] == ['註冊右鍵整合', '取消註冊右鍵整合']
    assert all(not action.isCheckable() for action in actions)


@pytest.mark.parametrize('index,expected', [(0, '已註冊右鍵整合。'), (1, '已取消註冊右鍵整合。')])
def test_menu_action_runs_selected_operation_and_reports_result(qtbot, monkeypatch, tmp_path, index, expected):
    window = main.MainWindow(); qtbot.addWidget(window)
    monkeypatch.setattr(main, 'confirmBox', lambda *a, **k: True)
    marker = tmp_path / 'operation.txt'
    def install(): marker.write_text('install'); return True
    def uninstall(): marker.write_text('uninstall'); return False
    monkeypatch.setattr(shell_integration, 'install', install)
    monkeypatch.setattr(shell_integration, 'uninstall', uninstall)
    menu(window).actions()[index].trigger()
    qtbot.waitUntil(lambda: not window.busy)
    assert marker.read_text() == ('install' if index == 0 else 'uninstall')
    assert window.summary.text() == expected
    assert all(action.isEnabled() for action in menu(window).actions())


def test_cancel_confirmation_does_not_change_shell(qtbot, monkeypatch):
    window = main.MainWindow(); qtbot.addWidget(window)
    monkeypatch.setattr(main, 'confirmBox', lambda *a, **k: False)
    def forbidden(): raise AssertionError('取消確認不得操作註冊')
    monkeypatch.setattr(shell_integration, 'uninstall', forbidden)
    menu(window).actions()[1].trigger()
    assert not window.busy and not window.workers


def test_busy_blocks_menu_and_direct_entry(qtbot, monkeypatch):
    window = main.MainWindow(); qtbot.addWidget(window)
    def forbidden(*a, **k): raise AssertionError('工作中不得詢問或重複操作')
    monkeypatch.setattr(main, 'confirmBox', forbidden)
    window.busy = True; window.update_controls()
    try:
        assert all(not action.isEnabled() for action in menu(window).actions())
        window.toggle_shell(False)
        assert not window.workers
    finally:
        window.busy = False; window.update_controls()


def test_failed_removal_reports_error_and_restores_actions(qtbot, monkeypatch):
    window = main.MainWindow(); qtbot.addWidget(window)
    monkeypatch.setattr(main, 'confirmBox', lambda *a, **k: True)
    def fail(): raise RuntimeError('測試移除失敗')
    monkeypatch.setattr(shell_integration, 'uninstall', fail)
    errors = []
    monkeypatch.setattr(main, 'msgCritical', lambda title, message, parent: errors.append(message))
    menu(window).actions()[1].trigger()
    qtbot.waitUntil(lambda: not window.busy)
    assert errors == ['測試移除失敗']
    assert all(action.isEnabled() for action in menu(window).actions())
    assert window.summary.text() != '已取消註冊右鍵整合。'
