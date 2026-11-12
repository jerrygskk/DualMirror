from PySide6.QtWidgets import QApplication


def test_defaults_and_saved_fonts(tmp_path):
    from lib.ui.font_settings import FontSettings
    settings = FontSettings(tmp_path / 'fonts.json')
    assert settings.tree == ('Microsoft JhengHei UI', 9)
    assert settings.content == ('Consolas', 10)
    settings.tree = ('Arial', 11); settings.content = ('Consolas', 12)
    settings.save()
    loaded = FontSettings(settings.path)
    assert loaded.tree == ('Arial', 11) and loaded.content == ('Consolas', 12)


def test_fonts_apply_to_existing_and_new_comparison_tabs(qtbot, tmp_path):
    from lib.ui.font_settings import FontSettings
    from lib.ui.main_window import MainWindow
    from lib.ui.hex_compare import HexCompare
    from lib.ui.text_compare import TextCompare
    window = MainWindow(); qtbot.addWidget(window)
    settings = FontSettings(tmp_path / 'fonts.json')
    settings.tree = ('Arial', 11); settings.content = ('Consolas', 12)
    left, right = tmp_path / 'a', tmp_path / 'b'
    for path in (left, right): path.write_bytes(b'hello')
    text = TextCompare(left, right, window.tabs); window.add_comparison_tab(text, (left, right))
    window.apply_fonts(settings)
    window.ensurePolished(); text.ensurePolished(); QApplication.processEvents()
    assert window.tree.font().pointSize() == 11
    assert text.left_edit.font().pointSize() == 12
    binary = HexCompare(left, right, window.tabs); window.add_comparison_tab(binary, (left, right))
    binary.ensurePolished(); QApplication.processEvents()
    assert binary.views[0].font().pointSize() == 12
    window.close()
    window.apply_fonts(FontSettings(tmp_path / 'defaults.json'))


def test_font_dialog_save_and_restore_defaults(qtbot, tmp_path):
    from lib.ui.font_settings import FontSettings, FontDialog, DEFAULT_CONTENT, DEFAULT_TREE
    from PySide6.QtGui import QFont
    settings = FontSettings(tmp_path / 'fonts.json')
    dialog = FontDialog(settings); qtbot.addWidget(dialog)
    dialog.controls[0][0].lineEdit().setText('Arial')
    dialog.controls[0][1].setValue(13)
    changed = dialog.values(); changed.save()
    assert FontSettings(settings.path).tree == ('Arial', 13)
    dialog.reset()
    assert dialog.values().tree == DEFAULT_TREE
    assert dialog.values().content == DEFAULT_CONTENT
    dialog.reject()
