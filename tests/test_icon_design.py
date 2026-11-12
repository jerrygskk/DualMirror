from main import MainWindow


def test_both_browse_buttons_precede_path(qtbot):
    window = MainWindow(); qtbot.addWidget(window)
    window.resize(1200, 700); window.show()
    for index, edit in enumerate((window.left_path, window.right_path)):
        folder, file = window.path_controls[index * 2:index * 2 + 2]
        assert folder.x() < file.x() < edit.x()
    window.close()


def test_vector_assets_match_design_source():
    import importlib.util
    from pathlib import Path
    from PySide6.QtSvg import QSvgRenderer
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location('icon_design', root / 'tools' / 'icon_design.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    for name, body in module.ICONS.items():
        path = root / 'assets' / 'icons' / f'{name}.svg'
        assert path.read_text(encoding='utf-8').strip() == module.svg(body).strip()
        assert QSvgRenderer(str(path)).isValid()
