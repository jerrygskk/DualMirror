import threading

import pytest
from PySide6.QtCore import QTimer
from lib.core.core import TextFile
from lib.ui.main_window import MainWindow


@pytest.mark.parametrize('binary', [False, True], ids=['text', 'hex'])
def test_reading_and_comparison_run_outside_ui_thread(qtbot, tmp_path, monkeypatch, binary):
    import lib.ui.main_window as main
    pair = (tmp_path / 'left', tmp_path / 'right')
    for path in pair: path.write_bytes(b'\0abc' if binary else b'hello\n')
    threads = []
    if binary:
        original = main.load_binary_comparison
        def load(paths):
            threads.append(threading.current_thread())
            return original(paths)
        monkeypatch.setattr(main, 'load_binary_comparison', load)
    else:
        original = TextFile.load
        def load(cls, path, **kwargs):
            threads.append(threading.current_thread())
            return original(path, **kwargs)
        monkeypatch.setattr(TextFile, 'load', classmethod(load))
    window = MainWindow(); qtbot.addWidget(window)
    window.open_file_pair(pair)
    qtbot.waitUntil(lambda: len(window.windows) == 1 and not window.busy)
    assert threads and all(thread is not threading.main_thread() for thread in threads)
    assert window.windows[0].file_pair == pair
    window.close()


def test_requests_wait_for_busy_job_without_losing_or_duplicating_pairs(qtbot, tmp_path):
    paths = [tmp_path / name for name in ('left', 'right', 'other')]
    for path in paths: path.write_text(path.name, encoding='utf-8')
    window = MainWindow(); qtbot.addWidget(window)
    release = threading.Event()
    window.run_job(lambda: release.wait(5), lambda _: None)
    try:
        window.open_file_pair(paths[:2])
        window.open_file_pair(paths[:2])
        window.open_file_pair((paths[0], paths[2]))
        heartbeat = []
        QTimer.singleShot(0, lambda: heartbeat.append(True))
        qtbot.waitUntil(lambda: bool(heartbeat))
        assert not window.windows
    finally:
        release.set()
        qtbot.waitUntil(lambda: not window.busy)
    qtbot.waitUntil(lambda: len(window.windows) == 2 and not window.busy)
    assert {page.file_pair for page in window.windows} == {
        (paths[0], paths[1]), (paths[0], paths[2])}
    window.close()
