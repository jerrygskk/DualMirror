"""本工具自製線條圖示與緊湊工具列元件。"""
from pathlib import Path
from PySide6.QtGui import QIcon, QColor
from PySide6.QtWidgets import QToolButton, QFrame, QStyledItemDelegate, QStyleOptionViewItem, QStyle
from PySide6.QtCore import Qt, QSize

ASSETS = Path(__file__).parent / 'assets' / 'icons'


class FolderSelectionDelegate(QStyledItemDelegate):
    """選取只改背景，保留檔名狀態色及圖示原色。"""
    def paint(self, painter, option, index):
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        if opt.state & QStyle.State_Selected:
            painter.fillRect(opt.rect, QColor('#DBECF9'))
            opt.state &= ~(QStyle.State_Selected | QStyle.State_MouseOver)
            opt.features &= ~QStyleOptionViewItem.Alternate
            opt.backgroundBrush = QColor('#DBECF9')
        super().paint(painter, opt, index)


def app_icon(name):
    path = ASSETS / f'{name}.svg'
    if not path.is_file():
        raise FileNotFoundError(f'缺少介面資源：{path.name}')
    return QIcon(str(path))


def tool_button(parent, title, name, checkable=False):
    button = QToolButton(parent)
    button.setToolTip(title)
    button.setAccessibleName(title)
    button.setText(title)
    button.setIcon(app_icon(name))
    button.setIconSize(QSize(16, 16))
    button.setToolButtonStyle(Qt.ToolButtonIconOnly)
    button.setFixedSize(28, 26)
    button.setCheckable(checkable)
    return button


def separator(layout):
    line = QFrame()
    line.setFrameShape(QFrame.VLine)
    line.setFixedHeight(22)
    layout.addWidget(line)
