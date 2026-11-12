from pathlib import Path
import importlib
import sys


ROOT = Path(__file__).resolve().parents[1]


def test_modules_import_from_organized_packages():
    for name in ('lib.application', 'lib.ui.main_window', 'lib.core.core',
                 'lib.settings.version', 'lib.integration.single_instance'):
        assert importlib.import_module(name)


def test_resources_resolve_independently_of_working_directory(monkeypatch, tmp_path):
    from lib.paths import resource_path
    monkeypatch.chdir(tmp_path)
    assert resource_path('assets/DualMirror.ico') == ROOT / 'assets/DualMirror.ico'
    assert resource_path('shell/AppxManifest.xml').is_file()


def test_frozen_resources_use_extraction_directory(monkeypatch, tmp_path):
    from lib.paths import resource_path
    monkeypatch.setattr(sys, '_MEIPASS', str(tmp_path), raising=False)
    assert resource_path('assets/icons/imgSpinUp.svg') == tmp_path / 'assets/icons/imgSpinUp.svg'
