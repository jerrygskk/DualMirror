import os
import random
from pathlib import Path
from PySide6.QtCore import Qt
from core import compare_paths, verify_contents
from hex_compare import HexCompare
from main import MainWindow
from comparison_gutter import content_result


def result_for(window, name):
    return content_result(window.item_pairs[name][0].data(0, Qt.UserRole))


def test_inserted_bytes_align_suffix_and_keep_real_addresses(qtbot, tmp_path):
    left, right = tmp_path / 'l', tmp_path / 'r'
    left.write_bytes(b'\x00ABCXYZDEF')
    right.write_bytes(b'\x00ABCDEF')
    w = HexCompare(left, right); qtbot.addWidget(w)
    assert w.blocks == [(4, 7)]
    assert w.models[1].data(w.models[1].index(0, 5)) == ''
    assert w.models[1].data(w.models[1].index(0, 8)) == '44'
    assert w.raw_offset(1, 7) == 4
    assert not w.is_difference(7)
    w.close()


def test_large_binary_multiple_shifts_reconstruct_originals():
    from binary_alignment import align_binary
    data = random.Random(1234).randbytes(20000)
    changed = data[:1500] + b'INSERT' + data[1500:12000] + data[12037:]
    layout = align_binary(data, changed)
    assert sum(end - start for start, end in layout.blocks) == 43
    for side, expected in enumerate((data, changed)):
        offsets = [layout.raw_offset(side, position) for position in range(layout.length)]
        offsets = [position for position in offsets if position is not None]
        assert offsets == list(range(len(expected)))


def test_hex_overview_click_jumps_and_reload_updates_red_ranges(qtbot, tmp_path):
    left, right = tmp_path / 'l', tmp_path / 'r'
    data = bytes(range(256)) * 64
    left.write_bytes(data); right.write_bytes(data[:12000] + b'NEW' + data[12000:])
    w = HexCompare(left, right); qtbot.addWidget(w)
    w.resize(1280, 650); w.show()
    assert w.overview.intervals()
    qtbot.mouseClick(w.overview, Qt.LeftButton, pos=w.overview.rect().center())
    assert w.views[0].verticalScrollBar().value() > 0
    from hex_compare import load_binary_comparison
    baseline = w.disk_baseline
    right.write_bytes(data)
    w.apply_disk_update(load_binary_comparison((left, right)), baseline)
    assert w.overview.intervals() == []
    assert not w.blocks
    w.close()


def test_result_column_only_appears_after_content_verification(qtbot, tmp_path):
    left, right = tmp_path / 'l', tmp_path / 'r'
    left.mkdir(); right.mkdir()
    for folder in (left, right): (folder / 'same').write_bytes(b'\0same')
    (left / 'diff').write_bytes(b'\0new'); (right / 'diff').write_bytes(b'\0old')
    w = MainWindow(); qtbot.addWidget(w)
    w.rows = compare_paths(left, right); w.render()
    assert result_for(w, 'same')[0] == ''
    w.rows = verify_contents(w.rows); w.render()
    assert result_for(w, 'same')[0] == '='
    assert result_for(w, 'diff')[0] == '≠'
    assert result_for(w, 'diff')[1] == '#e00000'
    w.close()


def test_open_hex_publishes_result_and_refresh_invalidates_it(qtbot, tmp_path):
    left, right = tmp_path / 'l', tmp_path / 'r'
    left.mkdir(); right.mkdir()
    a, b = left / 'item.bin', right / 'item.bin'
    a.write_bytes(b'\0abc'); b.write_bytes(b'\0xyz')
    stamp = a.stat(); os.utime(b, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    w = MainWindow(); qtbot.addWidget(w)
    w.left_path.setText(str(left)); w.right_path.setText(str(right)); w.compare()
    qtbot.waitUntil(lambda: not w.busy)
    assert result_for(w, 'item.bin')[0] == ''
    w.tree.setCurrentItem(w.tree.topLevelItem(0)); w.open_selected()
    qtbot.waitUntil(lambda: not w.busy and w.tabs.count() == 2)
    assert result_for(w, 'item.bin')[0] == '≠'
    w.close_tab(1)
    w.compare(); qtbot.waitUntil(lambda: not w.busy)
    assert result_for(w, 'item.bin')[0] == '≠'
    b.write_bytes(b'\0abc')
    w.compare(); qtbot.waitUntil(lambda: not w.busy)
    assert result_for(w, 'item.bin')[0] == ''
    w.close()


def test_alignment_empty_deleted_replaced_and_random_data_are_lossless():
    from binary_alignment import align_binary
    samples = [(b'', b''), (b'', b'abc'), (b'abc', b''), (b'abcXYZdef', b'abcdef'),
               (b'abcdef', b'abcUVWdef'), (b'\0' * 8000, b'\0' * 3000 + b'X' + b'\0' * 5000)]
    rng = random.Random(19)
    for _ in range(60):
        data = rng.randbytes(rng.randrange(1, 200))
        a, b = sorted((rng.randrange(len(data) + 1), rng.randrange(len(data) + 1)))
        samples.append((data, data[:a] + rng.randbytes(rng.randrange(20)) + data[b:]))
    for left, right in samples:
        layout = align_binary(left, right)
        recovered = [[], []]
        for slot in range(layout.length):
            offsets = [layout.raw_offset(side, slot) for side in (0, 1)]
            values = [data[offset] if offset is not None else None for data, offset in zip((left, right), offsets)]
            different = any(start <= slot < end for start, end in layout.blocks)
            assert different == (values[0] != values[1])
            for side, offset in enumerate(offsets):
                if offset is not None: recovered[side].append(offset)
        assert recovered == [list(range(len(left))), list(range(len(right)))]


def test_hex_row_addresses_use_original_offsets_after_insertion(qtbot, tmp_path):
    left, right = tmp_path / 'l', tmp_path / 'r'
    left.write_bytes(bytes(range(100)))
    right.write_bytes(bytes(range(8)) + b'INSERT' + bytes(range(8, 100)))
    w = HexCompare(left, right); qtbot.addWidget(w)
    assert w.blocks == [(8, 14)]
    assert w.models[0].data(w.models[0].index(1, 0)) == '0000000A'
    assert w.models[1].data(w.models[1].index(1, 0)) == '00000010'
    assert w.models[0].data(w.models[0].index(1, 1)) == '0A'
    assert w.models[1].data(w.models[1].index(1, 1)) == '0A'
    assert w.models[0].data(w.models[0].index(1, 1), Qt.ForegroundRole).name() == '#111111'
    w.close()


def test_file_notification_discards_content_cache_even_with_same_metadata(qtbot, tmp_path):
    left, right = tmp_path / 'l', tmp_path / 'r'
    left.mkdir(); right.mkdir()
    for folder in (left, right): (folder / 'same.bin').write_bytes(b'\0same')
    w = MainWindow(); qtbot.addWidget(w)
    w.left_path.setText(str(left)); w.right_path.setText(str(right)); w.compare()
    qtbot.waitUntil(lambda: not w.busy)
    w.rows = verify_contents(w.rows); w.render()
    assert result_for(w, 'same.bin')[0] == '='
    w.watcher.fileChanged.emit(str(left / 'same.bin'))
    qtbot.waitUntil(lambda: not w.busy and not w._refresh_pending)
    assert not w.rows[0].verified
    assert result_for(w, 'same.bin')[0] == ''
    w.close()
