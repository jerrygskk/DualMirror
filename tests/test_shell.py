from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def test_native_extension_accepts_exactly_two_files(tmp_path):
    binary = ROOT / 'shell' / 'FileCompareShell.dll'
    assert binary.is_file(), '尚未建置 Windows 右鍵擴充'
    result = subprocess.run([sys.executable, str(ROOT / 'tests' / 'native_probe.py'), str(tmp_path)],
                            capture_output=True, text=True, encoding='utf-8', timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
