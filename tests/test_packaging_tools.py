from pathlib import Path
from types import SimpleNamespace
import importlib.util
import pytest


ROOT = Path(__file__).resolve().parents[1]


def load_tool(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'tools' / f'{name}.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def test_version_tool_updates_only_temporary_copy_and_exe_metadata(tmp_path):
    tool = load_tool('bump_version')
    (tmp_path / 'version.py').write_bytes(b'APP_NAME = "DualMirror"\r\n__version__ = "0.1.0"\r\n')
    tool.update_version(tmp_path, '0.1.1')
    assert (tmp_path / 'version.py').read_bytes() == b'APP_NAME = "DualMirror"\r\n__version__ = "0.1.1"\r\n'
    from PyInstaller.utils.win32.versioninfo import load_version_info_from_text_file
    metadata = load_version_info_from_text_file(str(tmp_path / 'version_info.txt'))
    assert (metadata.ffi.fileVersionMS, metadata.ffi.fileVersionLS) == (1, 65536)
    assert 'DualMirror.exe' in str(metadata)
    assert '0.1.1' in str(metadata)


def test_version_cli_runs_from_other_directory_on_temporary_copy(tmp_path):
    import shutil
    import subprocess
    import sys
    (tmp_path / 'tools').mkdir()
    shutil.copyfile(ROOT / 'tools/bump_version.py', tmp_path / 'tools/bump_version.py')
    shutil.copyfile(ROOT / 'version.py', tmp_path / 'version.py')
    result = subprocess.run([sys.executable, str(tmp_path / 'tools/bump_version.py'), '0.2.0'],
                            cwd=tmp_path.parent, capture_output=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert '__version__ = "0.2.0"' in (tmp_path / 'version.py').read_text(encoding='utf-8')
    assert '0.2.0' in (tmp_path / 'version_info.txt').read_text(encoding='utf-8')


@pytest.mark.parametrize('version', ['1', '1.2.3.4.5', '1.2.-1', '65536.0.0', 'bad'])
def test_invalid_version_does_not_modify_files(tmp_path, version):
    tool = load_tool('bump_version')
    path = tmp_path / 'version.py'; path.write_bytes(b'__version__ = "0.1.0"\n')
    with pytest.raises(ValueError): tool.update_version(tmp_path, version)
    assert path.read_bytes() == b'__version__ = "0.1.0"\n'
    assert not (tmp_path / 'version_info.txt').exists()


def test_prune_preserves_runtime_plugins_ssl_and_uitools_dependencies():
    tool = load_tool('pyi_prune')
    required = ['Qt6Core.dll', 'Qt6Gui.dll', 'Qt6Widgets.dll', 'Qt6OpenGL.dll', 'Qt6OpenGLWidgets.dll',
                'Qt6UiTools.dll', 'Qt6Svg.dll', 'qsvg.dll', 'qsvgicon.dll', 'qico.dll', 'qwindows.dll',
                '_ssl.pyd', '_hashlib.pyd', 'libcrypto-3.dll', 'libssl-3.dll']
    analysis = SimpleNamespace(binaries=[(name, 'C:/Python/' + name, 'BINARY') for name in required] +
        [('Qt6Quick.dll', 'C:/Python/Qt6Quick.dll', 'BINARY'),
         ('libcrypto-3-x64.dll', 'C:/Program Files/Git/mingw64/bin/libcrypto-3-x64.dll', 'BINARY')],
        datas=[('PySide6/translations/qtbase_zh_TW.qm', '', 'DATA'),
               ('PySide6/translations/qtbase_fr.qm', '', 'DATA')])
    tool.prune(analysis, verbose=False)
    assert [entry[0] for entry in analysis.binaries] == required
    assert [entry[0] for entry in analysis.datas] == ['PySide6/translations/qtbase_zh_TW.qm']
    assert len(tool.force_qt_binaries()) == 2


def test_prune_rejects_tool_runtime_dlls_without_removing_formal_dependencies():
    tool = load_tool('pyi_prune')
    foreign = 'C:/Program Files/WindowsApps/OpenAI.CodexPrimaryRuntime.v26/dependencies/native/'
    required = [('PySide6/Qt6Core.dll', 'C:/Python/Lib/site-packages/PySide6/Qt6Core.dll', 'BINARY'),
                ('libcrypto-3.dll', 'C:/Python/DLLs/libcrypto-3.dll', 'BINARY')]
    analysis = SimpleNamespace(binaries=required + [
        ('icuuc.dll', foreign + 'poppler/Library/bin/icuuc.dll', 'BINARY'),
        ('ucrtbase.dll', foreign + 'libheif/bin/ucrtbase.dll', 'BINARY')],
        datas=[('libssl-3-x64.dll', foreign + 'poppler/Library/bin/libssl-3-x64.dll', 'DATA')])
    tool.prune(analysis, verbose=False)
    assert analysis.binaries == required
    assert analysis.datas == []


def test_spec_configuration_collects_real_resources_without_building(tmp_path):
    import runpy
    import shutil
    tool = load_tool('bump_version')
    # 不依賴被忽略的生成檔；在暫存專案複本重建 metadata。
    for folder in ('assets', 'shell'): shutil.copytree(ROOT / folder, tmp_path / folder)
    (tmp_path / 'tools').mkdir()
    for name in ('bump_version.py', 'pyi_prune.py'):
        shutil.copyfile(ROOT / 'tools' / name, tmp_path / 'tools' / name)
    for name in ('version.py', 'main.py', 'AppxManifest.xml'):
        shutil.copyfile(ROOT / name, tmp_path / name)
    tool.update_version(tmp_path)
    import sys
    previous = list(sys.path)
    try:
        # 只擷取宣告，不建立 Analysis 或執行 EXE 打包。
        namespace = runpy.run_path(str(ROOT / 'DualMirror.spec'), init_globals={
            'SPECPATH': str(tmp_path), 'Analysis': lambda *a, **k: SimpleNamespace(binaries=[], datas=[], pure=[], scripts=[], config=k),
            'PYZ': lambda *a, **k: None, 'EXE': lambda *a, **k: k})
    finally:
        sys.path[:] = previous
    exe = namespace['exe']; config = namespace['a'].config
    assert exe['name'] == 'DualMirror' and not exe['upx'] and not exe['console']
    assert Path(exe['icon']).is_file()
    destinations = {target for source, target in config['datas']}
    assert {'assets/icons', 'assets', 'shell', '.'} <= destinations
    for source, target in config['datas']: assert Path(source).exists()
    assert 'PySide6.QtUiTools' in config['hiddenimports']


def test_main_window_uses_version_source_and_loads_selected_icon(qtbot, monkeypatch):
    import main
    monkeypatch.setattr(main, 'APP_NAME', '測試產品')
    monkeypatch.setattr(main, '__version__', '2.3.4')
    w = main.MainWindow(); qtbot.addWidget(w)
    assert w.windowTitle() == '測試產品 v2.3.4'
    assert not w.windowIcon().isNull()
    assert w.windowIcon().pixmap(32, 32).toImage().hasAlphaChannel()
    w.close()
