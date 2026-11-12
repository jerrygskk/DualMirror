"""只在使用者啟用選項時註冊 Windows 11 右鍵擴充。"""
from pathlib import Path
import os
import subprocess
import sys
import locale
import hashlib
import shutil
import tempfile
import ctypes
from lib.settings.app_settings import data_folder
from lib.paths import PROJECT_ROOT, resource_path

ROOT = resource_path('')
POWERSHELL = Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32/WindowsPowerShell/v1.0/powershell.exe'


def command(mode, root=ROOT):
    if mode not in ('Status', 'Install', 'Remove'): raise ValueError('無效的整合操作。')
    body = (ROOT / 'shell/manage.ps1').read_text(encoding='utf-8')
    # 直接執行明確的命令，不更動本機腳本執行原則。
    literal = str(root).replace("'", "''")
    script = '& {\n' + body + "\n} -Mode '" + mode + "' -Root '" + literal + "'"
    return [str(POWERSHELL), '-NoProfile', '-NonInteractive', '-Command', script]


def decode_output(data):
    try: return data.decode('utf-8')
    except UnicodeDecodeError: return data.decode(locale.getpreferredencoding(False), errors='replace')


def run(mode, root=ROOT):
    # 變更註冊必須等 PowerShell 完成或自行回復，不能逾時強殺交易。
    result = subprocess.run(command(mode, root), capture_output=True,
                            timeout=60 if mode == 'Status' else None,
                            creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:
        raise RuntimeError('右鍵整合未完成。此功能需要 Windows 11 與已啟用的開發模式；程式不會自行修改安全設定。\n' + decode_output(result.stderr)[-1200:])
    if mode in ('Install', 'Remove'):
        ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, None, None)
    return decode_output(result.stdout).strip()


def installed():
    return run('Status') == 'installed'


RESOURCES = ('AppxManifest.xml',) + tuple('shell/' + name for name in
    ('FileCompareShell.dll', 'CompareLauncher.exe', 'Logo.png', 'Logo44.png', 'Logo150.png', 'Compare.ico'))


def resource_source(name):
    return ROOT / ('shell/AppxManifest.xml' if name == 'AppxManifest.xml' else name)


def prepare_resources():
    digest = hashlib.sha256()
    for name in RESOURCES:
        digest.update(name.encode('utf-8')); digest.update(resource_source(name).read_bytes())
    folder = data_folder() / 'shell'
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / digest.hexdigest()[:20]
    if target.exists():
        if all((target / name).read_bytes() == resource_source(name).read_bytes() for name in RESOURCES):
            return target
        raise RuntimeError('固定位置的右鍵元件已被修改，請移除整合後檢查。')
    stage = Path(tempfile.mkdtemp(prefix='prepare-', dir=folder))
    try:
        (stage / 'shell').mkdir()
        for name in RESOURCES: shutil.copyfile(resource_source(name), stage / name)
        stage.rename(target)
    finally:
        if stage.exists(): shutil.rmtree(stage)
    return target


def launch_configuration():
    if getattr(sys, 'frozen', False):
        return str(Path(sys.executable).resolve()) + '\n\n'
    python = Path(sys.executable).with_name('pythonw.exe')
    if not python.is_file(): raise RuntimeError('找不到目前 Python 的 pythonw.exe。')
    return str(python) + '\n' + str(PROJECT_ROOT / 'main.py') + '\n'


def install():
    launch = launch_configuration()
    root = prepare_resources()
    folder = data_folder()
    folder.mkdir(parents=True, exist_ok=True)
    config = folder / 'launcher.txt'
    previous = config.read_bytes() if config.exists() else None
    temporary = config.with_suffix('.tmp')
    temporary.write_text(launch, encoding='utf-8', newline='\n')
    temporary.replace(config)
    try:
        run('Install', root)
    except Exception:
        if previous is not None: config.write_bytes(previous)
        else: config.unlink(missing_ok=True)
        raise
    return True


def uninstall():
    run('Remove')
    return False
