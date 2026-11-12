"""獨立專案的正式 Python／直接相依快照，避免用另一支環境交付結果。"""
from pathlib import Path
from importlib.metadata import version
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]


def test_formal_python_is_pinned_x64_runtime():
    assert sys.version_info[:3] == (3, 12, 10)
    assert struct.calcsize('P') * 8 == 64


def test_pinned_packages_match_installed_runtime_and_build_tools():
    for name in ('requirements.txt', 'requirements-dev.txt'):
        for line in (ROOT / name).read_text(encoding='utf-8').splitlines():
            line = line.split('#', 1)[0].strip()
            if not line or line.startswith('-r '): continue
            package, expected = line.split('==')
            assert version(package) == expected, f'{package} 與已核定快照不同'
