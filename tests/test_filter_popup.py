import pytest
from PySide6.QtCore import QPoint, Qt
from main import MainWindow


@pytest.mark.parametrize('selected', [0, 3], ids=['first', 'lower'])
def test_filter_popup_opens_below_control_without_covering_toolbar(qtbot, selected):
    window = MainWindow(); qtbot.addWidget(window)
    window.resize(1280, 750); window.show(); qtbot.waitExposed(window)
    combo = window.filter_box
    combo.setCurrentIndex(selected)
    geometry = window.details_button.geometry()
    combo.showPopup()
    try:
        qtbot.waitUntil(lambda: combo.view().isVisible())
        popup = combo.view().window()
        # Qt joins the popup frame to the control's bottom border.
        bottom = combo.mapToGlobal(QPoint(0, combo.height() - 1)).y()
        assert popup.frameGeometry().top() >= bottom
        assert window.details_button.geometry() == geometry
        qtbot.keyClick(combo.view(), Qt.Key_Down)
        qtbot.keyClick(combo.view(), Qt.Key_Return)
        assert combo.currentIndex() == selected + 1
    finally:
        combo.hidePopup()
        window.close()
