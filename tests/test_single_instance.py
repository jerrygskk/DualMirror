from pathlib import Path
import pytest

from lib.ui.main_window import MainWindow


def folders(tmp_path, prefix):
    pair = tuple(tmp_path / (prefix + side) for side in ('left', 'right'))
    for path in pair:
        path.mkdir()
        (path / 'sample.txt').write_text(prefix, encoding='utf-8')
    return pair


def test_second_folder_request_preserves_first_session(qtbot, tmp_path):
    window = MainWindow(); qtbot.addWidget(window); window.show()
    first = folders(tmp_path, 'first')
    second = folders(tmp_path, 'second')
    window.open_startup_pair(first); qtbot.waitUntil(lambda: not window.busy)
    qtbot.waitUntil(lambda: not window.busy)
    window.search.setText('sample')
    window.open_request(second); qtbot.waitUntil(lambda: not window.busy)
    assert window.tabs.count() == 2
    session = window.tabs.currentWidget()
    qtbot.waitUntil(lambda: not session.busy)
    assert session.paths() == tuple(map(str, second))
    assert window.paths() == tuple(map(str, first))
    assert window.search.text() == 'sample'
    assert str(first[0]) in window.watcher.directories()
    assert str(second[0]) in session.watcher.directories()
    window.open_request(first); qtbot.waitUntil(lambda: not window.busy)
    assert window.tabs.count() == 2
    assert window.tabs.currentWidget() is window.folder_tab
    window.close_tab(window.tabs.indexOf(session))
    assert not session.watcher.directories()
    window.close()


def test_file_request_keeps_folder_and_unsaved_text(qtbot, tmp_path, monkeypatch):
    import lib.ui.text_compare as text_compare
    window = MainWindow(); qtbot.addWidget(window)
    pair = folders(tmp_path, 'folder')
    window.open_startup_pair(pair); qtbot.waitUntil(lambda: not window.busy)
    qtbot.waitUntil(lambda: not window.busy)
    files = tuple(path / 'sample.txt' for path in pair)
    window.open_request(files); qtbot.waitUntil(lambda: not window.busy)
    page = window.tabs.currentWidget()
    page.commit_text(0, 'unsaved\n')
    window.open_request(files); qtbot.waitUntil(lambda: not window.busy)
    assert window.tabs.count() == 2
    assert window.tabs.currentWidget() is page
    assert page.texts[0] == 'unsaved\n'
    window.open_request([]); qtbot.waitUntil(lambda: not window.busy)
    assert window.tabs.count() == 2
    monkeypatch.setattr(text_compare, 'confirmBox', lambda *a, **k: True)
    window.close()


def test_extra_folder_opens_shared_content_and_routes_menu(qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr('lib.ui.external_reload.confirmBox', lambda *a, **k: True)
    window = MainWindow(); qtbot.addWidget(window); window.show()
    window.open_startup_pair(folders(tmp_path, 'first')); qtbot.waitUntil(lambda: not window.busy)
    qtbot.waitUntil(lambda: not window.busy)
    pair = folders(tmp_path, 'second')
    window.open_request(pair); qtbot.waitUntil(lambda: not window.busy)
    session = window.tabs.currentWidget()
    qtbot.waitUntil(lambda: not session.busy)
    actions = window.menuBar().actions()
    view_action = next(action for action in actions if action.text() == '檢視')
    view_menu = view_action.menu()
    next(action for action in view_menu.actions() if action.text() == '差異').trigger()
    assert session.filter_box.currentIndex() == 1
    assert window.filter_box.currentIndex() == 0
    session.filter_box.setCurrentIndex(0)
    session.tree.setCurrentItem(session.tree.topLevelItem(0))
    session.open_selected(); qtbot.waitUntil(lambda: not window.busy)
    page = window.tabs.currentWidget()
    assert page.file_pair == tuple(path / 'sample.txt' for path in pair)
    assert len(window.windows) == 1 and window.tabs.count() == 3
    assert str(pair[0] / 'sample.txt') in window.watcher.files()
    window.open_request(pair); qtbot.waitUntil(lambda: not window.busy)
    session.open_selected(); qtbot.waitUntil(lambda: not window.busy)
    assert window.tabs.currentWidget() is page
    assert window.tabs.count() == 3
    window.close_tab(window.tabs.indexOf(window.folder_tab))
    assert str(pair[0] / 'sample.txt') in window.watcher.files()
    (pair[0] / 'sample.txt').write_text('external update', encoding='utf-8')
    window.external_reload.request()
    qtbot.waitUntil(lambda: page.texts[0] == 'external update', timeout=5000)
    qtbot.waitUntil(lambda: not window.busy and not session.busy)
    window.close()


@pytest.mark.parametrize('paths', [[], ['左 側.txt', '右側.txt']], ids=['activate', 'unicode_pair'])
def test_local_channel_delivers_unicode_pair_from_second_process(qtbot, tmp_path, paths):
    import os
    import subprocess
    import sys
    from lib.integration.single_instance import InstanceChannel
    channel = InstanceChannel(tmp_path)
    assert channel.start() is True
    received = []
    channel.requested.connect(received.append)
    script = Path(__file__).with_name('instance_client.py')
    process = subprocess.Popen([sys.executable, str(script), str(tmp_path), *paths],
                               cwd=Path(__file__).resolve().parents[1], env=os.environ.copy())
    try:
        qtbot.waitUntil(lambda: process.poll() is not None, timeout=15000)
        assert process.returncode == 0
        assert received == [paths]
    finally:
        if process.poll() is None: process.kill()
        process.wait()
        channel.close()
    replacement = InstanceChannel(tmp_path)
    assert replacement.start() is True
    replacement.close()


def test_hex_request_reuses_tab_without_removing_folder(qtbot, tmp_path):
    from lib.ui.hex_compare import HexCompare
    window = MainWindow(); qtbot.addWidget(window)
    window.open_startup_pair(folders(tmp_path, 'first')); qtbot.waitUntil(lambda: not window.busy)
    qtbot.waitUntil(lambda: not window.busy)
    pair = (tmp_path / 'left.bin', tmp_path / 'right.bin')
    pair[0].write_bytes(b'\0abc')
    pair[1].write_bytes(b'\0axc')
    window.open_request(pair); qtbot.waitUntil(lambda: not window.busy)
    page = window.tabs.currentWidget()
    assert isinstance(page, HexCompare)
    assert page.blocks == [(2, 3)]
    window.open_request(pair); qtbot.waitUntil(lambda: not window.busy)
    assert window.tabs.count() == 2 and window.tabs.currentWidget() is page
    window.close()


def test_incoming_hex_pair_during_background_open_does_not_duplicate(qtbot, tmp_path, monkeypatch):
    import threading
    import lib.ui.main_window as main
    pair = folders(tmp_path, 'folder')
    for folder in pair: (folder / 'binary.bin').write_bytes(b'\0abc')
    window = MainWindow(); qtbot.addWidget(window)
    window.open_startup_pair(pair)
    qtbot.waitUntil(lambda: not window.busy)
    original = main.load_binary_comparison
    started, release = threading.Event(), threading.Event()
    def load(paths):
        if threading.current_thread() is not threading.main_thread():
            started.set()
            if not release.wait(5): raise TimeoutError('test worker did not resume')
        return original(paths)
    monkeypatch.setattr(main, 'load_binary_comparison', load)
    window.tree.setCurrentItem(window.item_pairs['binary.bin'][0])
    window.open_selected()
    try:
        qtbot.waitUntil(started.is_set)
        files = tuple(folder / 'binary.bin' for folder in pair)
        window.open_request(files)
    finally:
        release.set()
        qtbot.waitUntil(lambda: not window.busy)
    assert len(window.windows) == 1
    assert window.tabs.count() == 2 and window.tabs.currentWidget().file_pair == files
    window.close()
