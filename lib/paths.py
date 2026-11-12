"""原始碼與單一執行檔共用的資源位置。"""
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def resource_path(relative):
    root = Path(getattr(sys, '_MEIPASS', PROJECT_ROOT))
    return root / relative
