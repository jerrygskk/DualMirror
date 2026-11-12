"""字型預設與使用者設定。"""
import json
import os
from pathlib import Path
from app_settings import font_settings_path
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QGroupBox,
    QFontComboBox, QSpinBox, QDialogButtonBox, QPushButton)

DEFAULT_TREE = ('Microsoft JhengHei UI', 9)
DEFAULT_CONTENT = ('Consolas', 10)


class FontSettings:
    def __init__(self, path=None):
        self.path = Path(path) if path is not None else font_settings_path()
        self.tree, self.content = DEFAULT_TREE, DEFAULT_CONTENT
        try:
            values = json.loads(self.path.read_text(encoding='utf-8'))
            for key in ('tree', 'content'):
                value = values.get(key)
                if (isinstance(value, list) and len(value) == 2 and isinstance(value[0], str)
                        and value[0] and isinstance(value[1], int) and 6 <= value[1] <= 36):
                    setattr(self, key, tuple(value))
        except (OSError, ValueError, TypeError, AttributeError): pass

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix('.tmp')
        temporary.write_text(json.dumps({'tree': self.tree, 'content': self.content}, ensure_ascii=False), encoding='utf-8')
        temporary.replace(self.path)

    def stylesheet(self):
        def rule(selectors, font):
            family, size = font
            family = family.replace('\\', '\\\\').replace('"', '\\"')
            return f'{selectors} {{ font-family: "{family}"; font-size: {size}pt; }}\n'
        return (rule('QTreeWidget, QTreeWidget QHeaderView', self.tree)
                + f'QTreeWidget::item {{ height: {max(18, round(self.tree[1] * 1.6) + 3)}px; }}\n'
                + rule('Editor, QTableView#hexView', self.content))


class FontDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent); self.setWindowTitle('字型設定'); self.resize(520, 350)
        self.setObjectName('fontSettingsDialog')
        self.settings = settings; self.controls = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)
        for title, font in (('檔案樹', settings.tree), ('文字／十六進位內容', settings.content)):
            group = QGroupBox(title); form = QFormLayout(group)
            form.setContentsMargins(12, 24, 12, 12)
            form.setVerticalSpacing(10)
            family = QFontComboBox(); family.setCurrentFont(QFont(font[0]))
            family.setCurrentText(font[0])
            size = QSpinBox(); size.setRange(6, 36); size.setValue(font[1]); size.setSuffix(' pt')
            form.addRow('字型', family); form.addRow('大小', size)
            layout.addWidget(group); self.controls.append((family, size))
        reset = QPushButton('還原預設值'); reset.clicked.connect(self.reset); layout.addWidget(reset)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText('套用'); buttons.button(QDialogButtonBox.Cancel).setText('取消')
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); layout.addWidget(buttons)
        self.controls[0][0].setFocus()

    def reset(self):
        for (family, size), default in zip(self.controls, (DEFAULT_TREE, DEFAULT_CONTENT)):
            family.setCurrentText(default[0]); size.setValue(default[1])

    def values(self):
        result = FontSettings(self.settings.path)
        result.tree, result.content = [(family.currentText().strip() or default[0], size.value())
            for (family, size), default in zip(self.controls, (DEFAULT_TREE, DEFAULT_CONTENT))]
        return result
