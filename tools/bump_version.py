"""移植自 PoliceDocSys／POS 的版本資訊產生機制，僅保留 DualMirror 所需內容。

指定版號：python tools/bump_version.py 0.1.0
重建資訊：python tools/bump_version.py --regenerate
不改 README，不建 tag、不打包、不發布。
"""
from pathlib import Path
import argparse
import re

ROOT = Path(__file__).resolve().parents[1]
VERSION_PATTERN = re.compile(r'(__version__\s*=\s*")([^"]*)(")')


def validate_version(version):
    if not re.fullmatch(r'\d+(?:\.\d+){1,3}', version):
        raise ValueError('版本號須為 2～4 段非負整數，例如 0.1.0。')
    parts = tuple(int(part) for part in version.split('.'))
    if any(part > 65535 for part in parts): raise ValueError('每段版號不得超過 65535。')
    return parts + (0,) * (4 - len(parts))


def read_current(root=ROOT):
    match = VERSION_PATTERN.search((Path(root) / 'lib/settings/version.py').read_text(encoding='utf-8'))
    if not match: raise ValueError('version.py 缺少 __version__。')
    validate_version(match.group(2))
    return match.group(2)


def render_info(version):
    numbers = validate_version(version)
    strings = {
        'FileDescription': 'DualMirror 檔案比較與合併', 'FileVersion': version,
        'InternalName': 'DualMirror', 'OriginalFilename': 'DualMirror.exe',
        'ProductName': 'DualMirror', 'ProductVersion': version,
    }
    values = ',\n'.join(f'          StringStruct({key!r}, {value!r})' for key, value in strings.items())
    return f'''# UTF-8
# 由 tools/bump_version.py 產生，請勿手改
VSVersionInfo(
  ffi=FixedFileInfo(filevers={numbers}, prodvers={numbers}, mask=0x3f,
                    flags=0, OS=0x40004, fileType=1, subtype=0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040404b0', [
{values}
    ])]),
    VarFileInfo([VarStruct('Translation', [1028, 1200])])
  ]
)
'''


def update_version(root=ROOT, version=None):
    root = Path(root)
    current = read_current(root)
    new = current if version is None else version.removeprefix('v')
    info = render_info(new)  # 先完整驗證，再寫入；保留原 version.py 換行。
    path = root / 'lib/settings/version.py'
    text = path.read_bytes().decode('utf-8')
    updated = VERSION_PATTERN.sub(lambda m: m.group(1) + new + m.group(3), text, count=1)
    if version is not None: path.write_bytes(updated.encode('utf-8'))
    destination = root / 'packaging/version_info.txt'
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(info.encode('utf-8'))
    return new


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('version', nargs='?')
    group.add_argument('--regenerate', action='store_true')
    args = parser.parse_args()
    try: version = update_version(version=args.version)
    except (OSError, ValueError) as error: parser.exit(1, str(error) + '\n')
    print(f'已產生 DualMirror {version} 的 EXE 版本資訊。')


if __name__ == '__main__': main()
