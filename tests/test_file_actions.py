import pytest
from lib.core.file_actions import selected_paths, rename_item


def test_selection_collapses_children_and_rejects_outside(tmp_path):
    folder = tmp_path / '資料夾'; folder.mkdir()
    child = folder / '檔案.txt'; child.write_text('test', encoding='utf-8')
    assert selected_paths(tmp_path, [child, folder]) == [folder]
    with pytest.raises(ValueError): selected_paths(folder, [tmp_path])


def test_rename_preserves_contents_and_refuses_collision(tmp_path):
    source = tmp_path / '原名.txt'; source.write_bytes(b'original')
    target = rename_item(source, '新名.txt')
    assert target.read_bytes() == b'original' and not source.exists()
    other = tmp_path / 'other.txt'; other.write_bytes(b'other')
    with pytest.raises(FileExistsError): rename_item(target, other.name)
    assert target.read_bytes() == b'original' and other.read_bytes() == b'other'


@pytest.mark.parametrize('name', ['', '..', '../a', 'a/b', 'CON.txt', 'a.', 'a ', 'x:y'])
def test_invalid_names_never_change_source(tmp_path, name):
    source = tmp_path / 'source'; source.mkdir()
    with pytest.raises(ValueError): rename_item(source, name)
    assert source.is_dir()
