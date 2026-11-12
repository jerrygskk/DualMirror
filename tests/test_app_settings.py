import json
from PySide6.QtCore import QSettings


def test_fonts_copy_legacy_without_overwriting_new(tmp_path, monkeypatch):
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path))
    old = tmp_path / 'FileComparePython' / 'fonts.json'
    old.parent.mkdir(); old.write_text('{"tree":["Arial",12]}', encoding='utf-8')
    from lib.ui.font_settings import FontSettings
    value = FontSettings()
    assert value.path == tmp_path / 'DualMirror' / 'fonts.json'
    assert value.tree == ('Arial', 12)
    assert old.exists()
    value.tree = ('Consolas', 11); value.save()
    assert FontSettings().tree == ('Consolas', 11)


def test_compare_settings_fill_missing_once(tmp_path):
    from lib.settings.app_settings import migrate_compare_settings
    old = QSettings(str(tmp_path / 'old.ini'), QSettings.IniFormat)
    new = QSettings(str(tmp_path / 'new.ini'), QSettings.IniFormat)
    old.setValue('method', 'rules'); old.setValue('case', True)
    new.setValue('method', 'crc')
    migrate_compare_settings(new, old)
    assert new.value('method') == 'crc'
    assert new.value('case', type=bool)
    old.setValue('space', True)
    migrate_compare_settings(new, old)
    assert not new.contains('space')
    assert old.value('method') == 'rules'
