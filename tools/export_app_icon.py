"""由正式 SVG 匯出透明多尺寸 ICO；保留圓滑邊緣，無需新套件。"""
from pathlib import Path
import struct
from PySide6.QtCore import Qt, QRectF, QBuffer, QIODevice
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

ROOT = Path(__file__).resolve().parents[1]


def export_icon(source, target):
    renderer = QSvgRenderer(str(source))
    if not renderer.isValid(): raise ValueError(f'SVG 無法讀取：{source}')
    master = QImage(2048, 2048, QImage.Format_ARGB32_Premultiplied)
    master.fill(Qt.transparent)
    painter = QPainter(master); painter.setRenderHint(QPainter.Antialiasing)
    renderer.render(painter, QRectF(0, 0, 2048, 2048)); painter.end()
    images = []
    for size in (16, 24, 32, 48, 64, 128, 256):
        image = master.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        buffer = QBuffer(); buffer.open(QIODevice.WriteOnly)
        if not image.save(buffer, 'PNG'): raise OSError('圖示 PNG 編碼失敗。')
        images.append((size, bytes(buffer.data())))
    offset = 6 + 16 * len(images)
    header = struct.pack('<HHH', 0, 1, len(images))
    for size, data in images:
        header += struct.pack('<BBBBHHII', size % 256, size % 256, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
    Path(target).write_bytes(header + b''.join(data for _, data in images))


if __name__ == '__main__':
    export_icon(ROOT / 'assets/DualMirror.svg', ROOT / 'assets/DualMirror.ico')
    print('已由正式 SVG 匯出 DualMirror.ico（16～256 像素）。')
