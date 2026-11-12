# -*- mode: python ; coding: utf-8 -*-
"""依 PoliceDocSys／POS 公版移植的 onefile 設定；正式打包命令見 docs/DEVELOPER.md。"""
from pathlib import Path
import sys

root = Path(SPECPATH).resolve().parent
sys.path.insert(0, str(root / 'tools'))
from pyi_prune import prune
from bump_version import read_current, render_info

info = root / 'packaging' / 'version_info.txt'
if not info.is_file() or info.read_text(encoding='utf-8') != render_info(read_current(root)):
    raise SystemExit('EXE 版本資訊缺少或不同步；請執行 python tools/bump_version.py --regenerate。')

datas = [(str(root / 'assets' / 'icons'), 'assets/icons'),
         (str(root / 'assets' / 'DualMirror.svg'), 'assets'),
         (str(root / 'assets' / 'DualMirror.ico'), 'assets'),
         (str(root / 'shell' / 'AppxManifest.xml'), 'shell')]
for name in ('manage.ps1', 'FileCompareShell.dll', 'CompareLauncher.exe', 'Logo.png', 'Logo44.png', 'Logo150.png', 'Compare.ico'):
    datas.append((str(root / 'shell' / name), 'shell'))
for source, _ in datas:
    if not Path(source).exists(): raise SystemExit(f'缺少打包資源：{source}')

a = Analysis(
    [str(root / 'main.py')], pathex=[str(root)], binaries=[], datas=datas,
    hiddenimports=['PySide6.QtSvg',
                   'pygments.styles.friendly', 'pygments.lexers.c_cpp', 'pygments.lexers.configs',
                   'pygments.lexers.css', 'pygments.lexers.data', 'pygments.lexers.dotnet',
                   'pygments.lexers.html', 'pygments.lexers.javascript', 'pygments.lexers.jvm',
                   'pygments.lexers.markup', 'pygments.lexers.python', 'pygments.lexers.shell',
                   'pygments.lexers.special', 'pygments.lexers.sql'], hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=['tkinter', 'pytest', 'matplotlib', 'numpy', 'PIL',
              'PySide6.QtQuick', 'PySide6.QtQuickWidgets', 'PySide6.QtQml',
              'PySide6.QtOpenGL', 'PySide6.QtOpenGLWidgets'],
    noarchive=False, optimize=0,
)
prune(a)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [], name='DualMirror', debug=False,
    bootloader_ignore_signals=False, strip=False, upx=False, upx_exclude=[],
    runtime_tmpdir=None, console=False, disable_windowed_traceback=False,
    argv_emulation=False, target_arch=None, codesign_identity=None, entitlements_file=None,
    icon=str(root / 'assets' / 'DualMirror.ico'), version=str(info),
)
