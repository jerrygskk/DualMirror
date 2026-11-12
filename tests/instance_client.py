"""獨立程序測試真正的本機比較請求傳送。"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QCoreApplication
from single_instance import InstanceChannel

app = QCoreApplication(sys.argv)
channel = InstanceChannel(Path(sys.argv[1]))
if channel.start():
    channel.close()
    raise SystemExit(2)
raise SystemExit(0 if channel.forward(sys.argv[2:]) else 3)
