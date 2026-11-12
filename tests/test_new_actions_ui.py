from PySide6.QtCore import Qt, QTimer, QSettings
from PySide6.QtWidgets import QApplication, QDialog, QInputDialog
from lib.ui.main_window import MainWindow
from lib.core.core import compare_paths, verify_contents
from lib.ui.compare_options import CompareOptions


def test_rule_and_crc_comparison(tmp_path):
    left, right = tmp_path / 'a', tmp_path / 'b'
    left.write_bytes(b'HELLO \r\n'); right.write_bytes(b'hello\n')
    rows = compare_paths(left, right)
    assert verify_contents(rows, method='crc')[0].status == 'different'
    assert verify_contents(rows, method='rules', rules=('case', 'space'))[0].status == 'same'
    assert verify_contents(rows, method='rules', rules=('case',))[0].status == 'different'
    right.write_bytes(left.read_bytes())
    assert verify_contents(rows, method='crc')[0].status == 'same'


def test_compare_options_counts_and_rule_controls(qtbot, tmp_path):
    left, right = tmp_path / 'a', tmp_path / 'b'
    left.write_bytes(b'a'); right.write_bytes(b'b')
    dialog = CompareOptions(compare_paths(left, right), None)
    qtbot.addWidget(dialog)
    dialog.methods[2][1].setChecked(True)
    assert all(check.isEnabled() for _, check in dialog.rules)
    dialog.rules[0][1].setChecked(True)
    assert dialog.options()[0] == 'rules'
    assert 'case' in dialog.options()[1]
    dialog.reject()


def test_single_side_rename_refreshes_and_keeps_other(qtbot, tmp_path):
    left, right = tmp_path / 'left', tmp_path / 'right'
    left.mkdir(); right.mkdir()
    for root in (left, right): (root / 'old.txt').write_bytes(b'original')
    window = MainWindow(); qtbot.addWidget(window)
    window.left_path.setText(str(left)); window.right_path.setText(str(right))
    window.compare(); qtbot.waitUntil(lambda: not window.busy)
    window.tree.topLevelItem(0).setSelected(True)
    window.active_tree_side = 1
    def rename():
        dialog = QApplication.activeModalWidget()
        assert isinstance(dialog, QInputDialog)
        dialog.setTextValue('new.txt'); dialog.accept()
    QTimer.singleShot(20, rename)
    window.rename_selected()
    qtbot.waitUntil(lambda: (right / 'new.txt').exists() and not window.busy)
    qtbot.waitUntil(lambda: len(window.rows) == 2 and not window.busy)
    assert (left / 'old.txt').read_bytes() == b'original'
    assert not (right / 'old.txt').exists()
    window.close()


def test_pre_post_compare_colors(qtbot, tmp_path):
    import os
    left, right = tmp_path / 'left', tmp_path / 'right'
    left.mkdir(); right.mkdir()
    (left / 'a').write_bytes(b'a'); (right / 'a').write_bytes(b'a')
    os.utime(left / 'a', ns=(1000000000, 1000000000))
    window = MainWindow(); qtbot.addWidget(window)
    window.left_path.setText(str(left)); window.right_path.setText(str(right))
    window.compare(); qtbot.waitUntil(lambda: not window.busy)
    assert window.item_pairs['a'][0].foreground(0).color().name() == '#808080'
    assert window.item_pairs['a'][1].foreground(0).color().name() == '#ff0000'
    window.rows = verify_contents(window.rows); window.render()
    assert all(item.foreground(0).color().name() == '#000000' for item in window.item_pairs['a'])
    window.close()


def test_delete_handler_uses_clicked_side_and_refreshes(qtbot, tmp_path, monkeypatch):
    import lib.core.file_actions as file_actions
    import lib.ui.main_window as main
    left, right = tmp_path / 'left', tmp_path / 'right'
    left.mkdir(); right.mkdir()
    for root in (left, right): (root / 'a.txt').write_bytes(b'keep')
    window = MainWindow(); qtbot.addWidget(window)
    window.left_path.setText(str(left)); window.right_path.setText(str(right))
    window.compare(); qtbot.waitUntil(lambda: not window.busy)
    window.tree.topLevelItem(0).setSelected(True); window.active_tree_side = 1
    monkeypatch.setattr(main, 'confirmBox', lambda *a, **k: False)
    window.delete_selected()
    assert (right / 'a.txt').exists()
    calls = []
    def recycle(paths):
        calls.extend(paths)
        # 暫存複本移到測試保留區，真實 Windows 回收另由 smoke 驗證。
        paths[0].rename(tmp_path / 'recycled.txt')
    monkeypatch.setattr(file_actions, 'recycle_items', recycle)
    monkeypatch.setattr(main, 'confirmBox', lambda *a, **k: True)
    window.delete_selected()
    qtbot.waitUntil(lambda: not window.busy and calls != [])
    qtbot.waitUntil(lambda: window.rows[0].status == 'left' and not window.busy)
    assert calls == [right / 'a.txt']
    assert (left / 'a.txt').read_bytes() == b'keep'
    window.close()
