"""DualMirror 設定位置及既有真實設定的一次性保留。"""
import os
from pathlib import Path
from PySide6.QtCore import QSettings


def data_folder():
    return Path(os.environ['LOCALAPPDATA']) / 'DualMirror'


def font_settings_path():
    target = data_folder() / 'fonts.json'
    legacy = target.parent.parent / 'FileComparePython' / 'fonts.json'
    if not target.exists() and legacy.is_file():
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            with target.open('xb') as stream: stream.write(legacy.read_bytes())
        except FileExistsError:
            pass
    return target


def migrate_compare_settings(target, legacy):
    if target.value('_legacy_imported', False, type=bool): return target
    for key in ('method', 'case', 'space', 'newlines', 'results', 'skip'):
        if not target.contains(key) and legacy.contains(key):
            target.setValue(key, legacy.value(key))
    target.setValue('_legacy_imported', True)
    target.sync()
    if target.status() != QSettings.NoError:
        raise OSError('無法儲存比較設定，舊設定仍保留。')
    return target


def compare_settings():
    return migrate_compare_settings(QSettings('DualMirror', 'CompareContents'),
                                    QSettings('FileComparePython', 'CompareContents'))
