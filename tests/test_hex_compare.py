from PySide6.QtCore import Qt
from main import MainWindow


def test_binary_opens_in_same_window_and_reuses_tab(qtbot, tmp_path, monkeypatch):
    import main
    monkeypatch.setattr(main, 'msgInfo', lambda *args: None)
    left, right = tmp_path / 'left.bin', tmp_path / 'right.bin'
    left.write_bytes(b'\0abc'); right.write_bytes(b'\0axc')
    window = MainWindow(); qtbot.addWidget(window)
    window.left_path.setText(str(left)); window.right_path.setText(str(right))
    window.compare(); qtbot.waitUntil(lambda: not window.busy)
    window.tree.topLevelItem(0).setSelected(True)
    window.open_selected(); qtbot.waitUntil(lambda: not window.busy)
    assert window.tabs.count() == 2
    tab = window.tabs.currentWidget()
    assert tab.models[0].data(tab.models[0].index(0, 3)) == '62'
    assert tab.blocks == [(2, 3)]
    window.open_selected(); assert window.tabs.count() == 2
    window.close()


def test_hex_missing_side_and_navigation(qtbot, tmp_path):
    from hex_compare import HexCompare
    left, right = tmp_path / 'left.bin', tmp_path / 'missing.bin'
    left.write_bytes(b'\x00ABC' + b'x' * 30)
    tab = HexCompare(left, right, documents=(left.read_bytes(), None))
    qtbot.addWidget(tab)
    assert not tab.views[1].isEnabled()
    assert tab.models[0].data(tab.models[0].index(0, 1)) == '00'
    assert tab.models[0].data(tab.models[0].index(0, 17)).startswith('.ABC')
    assert tab.blocks == [(0, 34)]
    tab.navigate(1)
    assert tab.views[0].currentIndex().row() == 0
    tab.close()


def test_difference_ranges_include_extra_bytes():
    from hex_compare import difference_ranges
    assert difference_ranges(b'abcd', b'axcde') == [(1, 2), (4, 5)]
    assert difference_ranges(b'', b'') == []
    assert difference_ranges(b'abc', b'abc') == []


def test_hex_external_change_refreshes_open_tab(qtbot, tmp_path):
    from hex_compare import HexCompare
    left, right = tmp_path / 'left', tmp_path / 'right'
    left.mkdir(); right.mkdir()
    for root in (left, right): (root / 'a.bin').write_bytes(b'\0abc')
    window = MainWindow(); qtbot.addWidget(window)
    window.left_path.setText(str(left)); window.right_path.setText(str(right))
    window.compare(); qtbot.waitUntil(lambda: not window.busy)
    window.tree.topLevelItem(0).setSelected(True); window.open_selected()
    qtbot.waitUntil(lambda: not window.busy)
    tab = window.tabs.currentWidget(); assert isinstance(tab, HexCompare)
    (right / 'a.bin').write_bytes(b'\0axc!')
    qtbot.waitUntil(lambda: not window.busy and tab.blocks == [(2, 3), (4, 5)], timeout=10000)
    assert tab.models[1].data(tab.models[1].index(0, 3), Qt.ForegroundRole).name() == '#d00000'
    assert tab.models[1].data(tab.models[1].index(0, 2), Qt.ForegroundRole).name() == '#111111'
    window.close()


def test_hex_is_readonly_and_navigation_wraps(qtbot, tmp_path):
    from hex_compare import HexCompare
    paths = (tmp_path / 'a', tmp_path / 'b')
    for path, data in zip(paths, (b'\0abc', b'\0xbz')): path.write_bytes(data)
    tab = HexCompare(*paths); qtbot.addWidget(tab)
    tab.resize(1280, 650); tab.show()
    assert not tab.models[0].flags(tab.models[0].index(0, 1)) & Qt.ItemIsEditable
    tab.navigate(1); assert tab.current == 0
    tab.navigate(1); assert tab.current == 1
    tab.navigate(1); assert tab.current == 0
    tab.navigate(-1); assert tab.current == 1
    assert [path.read_bytes() for path in paths] == [b'\0abc', b'\0xbz']
    tab.close()
