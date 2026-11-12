"""所有測試的使用者設定均限定在暫存目錄，不讀寫真實設定。"""
import pytest
from PySide6.QtCore import QSettings


@pytest.fixture(autouse=True)
def isolated_user_settings(tmp_path, monkeypatch):
    import compare_options
    from app_settings import migrate_compare_settings
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path / 'appdata'))
    def settings():
        return migrate_compare_settings(
            QSettings(str(tmp_path / 'compare.ini'), QSettings.IniFormat),
            QSettings(str(tmp_path / 'legacy.ini'), QSettings.IniFormat))
    monkeypatch.setattr(compare_options, 'compare_settings', settings)
