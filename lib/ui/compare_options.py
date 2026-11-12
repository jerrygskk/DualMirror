"""詳細比較選項，沿用全域樣式。"""
from PySide6.QtCore import QSettings
from lib.settings.app_settings import compare_settings
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QRadioButton, QCheckBox, QDialogButtonBox, QGroupBox)


class CompareOptions(QDialog):
    def __init__(self, rows, selected, parent=None):
        super().__init__(parent)
        self.setWindowTitle('比較內容'); self.resize(460, 360)
        self.settings = compare_settings()
        layout = QVBoxLayout(self)
        chosen = [row for row in rows if selected is None or row.relative in selected
                  or any(row.relative.startswith(name + '/') for name in selected)]
        counts = QHBoxLayout()
        for side in ('left', 'right'):
            present = [row for row in chosen if getattr(row, side).exists()]
            files = [row for row in present if not getattr(row, side).is_dir()]
            total = sum(getattr(row, side + '_size') or 0 for row in files)
            counts.addWidget(QLabel(f'{"左側" if side == "left" else "右側"}\n'
                f'{len(files)} 個檔案\n{len(present) - len(files)} 個資料夾\n{total:,} 位元組'))
        layout.addLayout(counts)
        group = QGroupBox('比較方式'); choices = QVBoxLayout(group)
        self.methods = []
        for key, text in (('crc', 'CRC 比較'), ('binary', '逐位元組比較'), ('rules', '依規則比較')):
            button = QRadioButton(text); choices.addWidget(button); self.methods.append((key, button))
            button.setChecked(key == self.settings.value('method', 'binary'))
        layout.addWidget(group)
        self.rules = []
        for key, text in (('case', '忽略大小寫'), ('space', '忽略空白'), ('newlines', '忽略換行格式')):
            check = QCheckBox(text); layout.addWidget(check); self.rules.append((key, check))
            check.setChecked(self.settings.value(key, False, type=bool))
        for _, button in self.methods: button.toggled.connect(self.update_rules)
        self.update_rules()
        self.result_box = QCheckBox('顯示結果摘要'); layout.addWidget(self.result_box)
        self.result_box.setChecked(self.settings.value('results', False, type=bool))
        self.skip_box = QCheckBox('不再顯示此視窗'); layout.addWidget(self.skip_box)
        self.skip_box.setChecked(self.settings.value('skip', False, type=bool))
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText('開始')
        buttons.button(QDialogButtonBox.Cancel).setText('取消')
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject)
        layout.addWidget(buttons); buttons.button(QDialogButtonBox.Ok).setFocus()

    def update_rules(self):
        enabled = self.methods[2][1].isChecked()
        for _, check in self.rules: check.setEnabled(enabled)

    def options(self):
        return (next(key for key, button in self.methods if button.isChecked()),
                tuple(key for key, check in self.rules if check.isChecked()), self.result_box.isChecked())

    def accept(self):
        method, rules, results = self.options()
        self.settings.setValue('method', method); self.settings.setValue('results', results)
        self.settings.setValue('skip', self.skip_box.isChecked())
        for key, _ in self.rules: self.settings.setValue(key, key in rules)
        super().accept()
