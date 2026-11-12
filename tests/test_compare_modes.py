import os
from pathlib import Path
from PySide6.QtCore import Qt
from lib.core.core import compare_paths
from lib.ui.main_window import MainWindow


def same_metadata(left, right):
    stamp = left.stat()
    os.utime(right, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))


def test_quick_compare_never_reads_file_contents(tmp_path, monkeypatch):
    left, right = tmp_path / 'l', tmp_path / 'r'
    left.write_bytes(b'abc'); right.write_bytes(b'xyz')
    same_metadata(left, right)
    def forbidden(*args, **kwargs): raise AssertionError('快速比較不應讀取檔案內容')
    with monkeypatch.context() as patch:
        patch.setattr(Path, 'open', forbidden)
        rows = compare_paths(left, right)
    assert rows[0].status == 'same'
    assert not rows[0].verified


def test_detailed_compare_finds_same_metadata_different_content(tmp_path):
    from lib.core.core import verify_contents
    left, right = tmp_path / 'l', tmp_path / 'r'
    left.write_bytes(b'abc'); right.write_bytes(b'xyz')
    same_metadata(left, right)
    rows = verify_contents(compare_paths(left, right))
    assert rows[0].status == 'different'
    assert rows[0].verified


def test_sync_still_checks_content_even_when_metadata_matches(tmp_path):
    from lib.core.core import sync_plan, execute_plan
    left, right = tmp_path / 'l', tmp_path / 'r'
    left.write_bytes(b'abc'); right.write_bytes(b'xyz')
    same_metadata(left, right)
    plan = sync_plan(left, right)
    assert len(plan) == 1
    execute_plan(plan)
    assert right.read_bytes() == b'abc'


def test_detailed_compare_overrides_different_timestamps(tmp_path):
    left, right = tmp_path / 'l', tmp_path / 'r'
    left.write_bytes(b'same'); right.write_bytes(b'same')
    stamp = left.stat()
    os.utime(right, ns=(stamp.st_atime_ns, stamp.st_mtime_ns + 10_000_000_000))
    assert compare_paths(left, right)[0].status == 'different'
    result = compare_paths(left, right, detailed=True)[0]
    assert result.status == 'same' and result.verified


def test_details_button_checks_selection_then_all(qtbot, tmp_path, monkeypatch):
    from lib.ui.compare_options import CompareOptions
    from PySide6.QtWidgets import QDialog
    monkeypatch.setattr(CompareOptions, 'exec', lambda self: QDialog.Accepted)
    monkeypatch.setattr(CompareOptions, 'options', lambda self: ('binary', (), False))
    left, right = tmp_path / 'l', tmp_path / 'r'
    left.mkdir(); right.mkdir()
    for name in ('one.txt', 'two.txt'):
        (left / name).write_bytes(b'abc'); (right / name).write_bytes(b'xyz')
        same_metadata(left / name, right / name)
    window = MainWindow(); qtbot.addWidget(window)
    window.left_path.setText(str(left)); window.right_path.setText(str(right))
    window.compare(); qtbot.waitUntil(lambda: not window.busy, timeout=10000)
    assert all(row.status == 'same' and not row.verified for row in window.rows)
    window.tree.setCurrentItem(window.tree.topLevelItem(0))
    qtbot.mouseClick(window.details_button, Qt.LeftButton)
    qtbot.waitUntil(lambda: not window.busy, timeout=10000)
    assert sum(row.verified for row in window.rows) == 1
    assert sum(row.status == 'different' for row in window.rows) == 1
    window.tree.clearSelection()
    qtbot.mouseClick(window.details_button, Qt.LeftButton)
    qtbot.waitUntil(lambda: not window.busy, timeout=10000)
    assert all(row.status == 'different' and row.verified for row in window.rows)
    window.close()
