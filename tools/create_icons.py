"""產生本工具自製的統一線條 SVG 圖示。"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'assets' / 'icons'
ROOT.mkdir(parents=True, exist_ok=True)
from icon_design import ICONS, svg

for name, body in ICONS.items():
    (ROOT / f'{name}.svg').write_text(svg(body) + '\n', encoding='utf-8')
print(f'Created {len(ICONS)} original SVG icons')

# Shell 的封裝標誌與 ICO 同樣由自製向量圖示產生。
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer
import struct
shell = ROOT.parents[1] / 'shell'
shell.mkdir(exist_ok=True)
renderer = QSvgRenderer(str(ROOT / 'imgTextCompareSession.svg'))
for size, filename in ((50, 'Logo.png'), (150, 'Logo150.png'), (44, 'Logo44.png'), (32, 'icon32.png')):
    image = QImage(size, size, QImage.Format_ARGB32)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    renderer.render(painter, QRectF(0, 0, size, size))
    painter.end()
    image.save(str(shell / filename), 'PNG')
raw = (shell / 'icon32.png').read_bytes()
(shell / 'Compare.ico').write_bytes(struct.pack('<HHH', 0, 1, 1) + struct.pack('<BBBBHHII', 32, 32, 0, 0, 1, 32, len(raw), 22) + raw)
(shell / 'icon32.png').unlink()
