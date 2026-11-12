import os
from PySide6.QtCore import Qt
from lib.core.core import compare_paths, verify_contents
from lib.ui.main_window import MainWindow


def samples(tmp_path):
    left, right = tmp_path / 'left', tmp_path / 'right'
    for root in (left, right):
        for name in ('same', 'newer', 'only_contents', 'mixed', 'gray_purple', 'parent/nested'):
            (root / name).mkdir(parents=True)
    def pair(name, a=b'same', b=b'same'):
        for root, data, stamp in ((left, a, 2000000000), (right, b, 1000000000)):
            path = root / name; path.write_bytes(data)
            os.utime(path, ns=(stamp, stamp))
        if a == b: os.utime(right / name, ns=(2000000000, 2000000000))
    pair('same/file.txt')
    pair('newer/file.txt', b'new', b'old')
    (right / 'only_contents/only.txt').write_bytes(b'right')
    pair('mixed/file.txt', b'new', b'old')
    (left / 'mixed/only.txt').write_bytes(b'left')
    pair('gray_purple/file.txt')
    (left / 'gray_purple/only.txt').write_bytes(b'left')
    pair('parent/nested/file.txt', b'new', b'old')
    return left, right


def test_folder_icons_summarize_each_side_without_using_folder_dates(tmp_path):
    from lib.ui.folder_presentation import summarize_folders
    rows = compare_paths(*samples(tmp_path))
    styles, totals = summarize_folders(rows)
    assert styles['same'] == ('gray', 'gray')
    assert styles['newer'] == ('red', 'gray')
    assert styles['only_contents'] == ('gray', 'purple')
    assert styles['mixed'] == ('red_purple', 'gray')
    assert styles['gray_purple'] == ('gray_purple', 'gray')
    assert styles['parent'] == ('red', 'gray')
    assert totals['mixed'] == (7, 3)


def test_folder_names_and_metadata_remain_neutral_while_files_keep_status_colors(qtbot, tmp_path):
    window = MainWindow(); qtbot.addWidget(window)
    left, right = samples(tmp_path)
    window.left_path.setText(str(left)); window.right_path.setText(str(right))
    window.compare(); qtbot.waitUntil(lambda: not window.busy)
    for name in ('newer', 'mixed', 'gray_purple', 'only_contents'):
        for item in window.item_pairs[name]:
            assert item.foreground(0).color().name() == '#000000'
            assert item.foreground(1).color().name() == '#808080'
            assert item.foreground(2).color().name() == '#808080'
    assert window.item_pairs['newer/file.txt'][0].foreground(0).color().name() == '#ff0000'
    assert window.item_pairs['newer/file.txt'][1].foreground(0).color().name() == '#808080'
    assert window.item_pairs['mixed/only.txt'][0].foreground(0).color().name() == '#285b83'
    assert window.item_pairs['mixed'][0].text(1) == '7'
    window.close()


def test_verified_equal_content_removes_newer_folder_hint(tmp_path):
    from lib.ui.folder_presentation import summarize_folders
    left, right = samples(tmp_path)
    (right / 'newer/file.txt').write_bytes(b'new')
    os.utime(right / 'newer/file.txt', ns=(1000000000, 1000000000))
    rows = verify_contents(compare_paths(left, right))
    assert summarize_folders(rows)[0]['newer'] == ('gray', 'gray')


def test_mixed_folder_icons_render_both_colors(qapp):
    from lib.ui.ui_assets import app_icon
    for style, colors in (('gray_purple', {'#d3d6da', '#3977a7'}),
                          ('red_purple', {'#f1b5af', '#3977a7'})):
        image = app_icon('imgFolder_' + style).pixmap(20, 20).toImage()
        actual = {image.pixelColor(x, y).name() for x in range(image.width()) for y in range(image.height())}
        assert colors <= actual
