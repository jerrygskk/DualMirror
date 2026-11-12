import pytest
from PySide6.QtCore import Qt, QPoint
from PySide6.QtWidgets import QApplication, QDialog, QComboBox, QFontComboBox, QVBoxLayout
from lib.ui.theme import APP_STYLE


@pytest.mark.parametrize('combo_type', [QComboBox, QFontComboBox])
def test_dropdown_arrow_is_visible_and_opens(qtbot, combo_type):
    QApplication.instance().setStyleSheet(APP_STYLE)
    dialog = QDialog(); qtbot.addWidget(dialog)
    layout = QVBoxLayout(dialog); combo = combo_type(); layout.addWidget(combo)
    if combo_type is QComboBox: combo.addItems(['全部檔案', '差異'])
    elif combo.count() == 0: combo.addItem('Sans Serif')  # offscreen 沒有系統字型。
    dialog.resize(300, 80); dialog.show(); qtbot.waitExposed(dialog)
    picture = combo.grab().toImage()
    center = picture.height() // 2
    dark = sum(picture.pixelColor(x, y).lightness() < 120
        for x in range(picture.width() - 16, picture.width() - 3)
        for y in range(center - 4, center + 5))
    assert dark >= 8, '下拉按鈕中央必須可見箭頭'
    qtbot.mouseClick(combo, Qt.LeftButton, pos=combo.rect().topRight() + QPoint(-8, combo.height() // 2))
    assert combo.view().isVisible()
    combo.hidePopup(); dialog.close()
