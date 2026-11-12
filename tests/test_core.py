from pathlib import Path
import codecs
import pytest
from core import compare_paths, TextFile, differences, merge_block, copy_checked, sync_plan, execute_plan


def test_compare_same_size_different_content(tmp_path):
    a, b = tmp_path / 'a', tmp_path / 'b'
    a.mkdir(); b.mkdir()
    (a / 'x.txt').write_bytes(b'abc')
    (b / 'x.txt').write_bytes(b'abd')
    (a / 'only').write_bytes(b'')
    rows = {r.relative: r for r in compare_paths(a, b, detailed=True)}
    assert rows['x.txt'].status == 'different'
    assert rows['only'].status == 'left'
    assert rows['x.txt'].left_size == 3


@pytest.mark.parametrize('raw,codec', [(b'a\r\nb\r\n', 'utf-8'), (codecs.BOM_UTF8 + '中文\r\n'.encode(), 'utf-8-sig'), ('中文\r\n'.encode('utf-16'), 'utf-16'), ('中文\r\n'.encode('cp950'), 'cp950')], ids=['utf8','bom','utf16','cp950'])
def test_text_roundtrip(tmp_path, raw, codec):
    p = tmp_path / 'text'; p.write_bytes(raw)
    doc = TextFile.load(p)
    assert doc is not None
    assert doc.encoding == codec
    doc.save(doc.text)
    assert p.read_bytes() == raw


def test_binary_is_not_text(tmp_path):
    p = tmp_path / 'bin'; p.write_bytes(b'\x00\xff\x01')
    assert TextFile.load(p) is None


def test_block_copy_insert_replace_delete():
    left, right = 'a\nnew\nc\n', 'a\nold\nc\n'
    block = differences(left, right)[0]
    assert merge_block(left, right, block, 'right') == left
    assert merge_block(left, right, block, 'left') == right
    left, right = 'a\nb\n', 'a\n'
    assert merge_block(left, right, differences(left, right)[0], 'right') == left
    assert merge_block(left, right, differences(left, right)[0], 'left') == right


def test_external_change_blocks_save_and_copy(tmp_path):
    p, q = tmp_path / 'p', tmp_path / 'q'
    p.write_bytes(b'old'); q.write_bytes(b'dest')
    doc = TextFile.load(p)
    plan = sync_plan(p, q)
    p.write_bytes(b'new')
    with pytest.raises(RuntimeError): doc.save('edited')
    with pytest.raises(RuntimeError): execute_plan(plan)
    assert p.read_bytes() == b'new'
    assert q.read_bytes() == b'dest'


def test_sync_preserves_extras_and_nested(tmp_path):
    a, b = tmp_path / 'a', tmp_path / 'b'
    (a / 'sub').mkdir(parents=True); b.mkdir()
    (a / 'sub' / 'x').write_bytes(b'new')
    (a / 'common').write_bytes(b'new')
    (b / 'common').write_bytes(b'old')
    (b / 'extra').write_bytes(b'keep')
    execute_plan(sync_plan(a, b))
    assert (b / 'sub' / 'x').read_bytes() == b'new'
    assert (b / 'common').read_bytes() == b'new'
    assert (b / 'extra').read_bytes() == b'keep'


def test_target_external_change_is_preserved(tmp_path):
    a, b = tmp_path / 'a', tmp_path / 'b'
    a.write_bytes(b'source'); b.write_bytes(b'original')
    plan = sync_plan(a, b)
    b.write_bytes(b'changed')
    with pytest.raises(RuntimeError): execute_plan(plan)
    assert b.read_bytes() == b'changed'


def test_nested_roots_rejected(tmp_path):
    (tmp_path / 'sub').mkdir()
    with pytest.raises(ValueError): sync_plan(tmp_path, tmp_path / 'sub')


def test_file_directory_conflict(tmp_path):
    a, b = tmp_path / 'a', tmp_path / 'b'
    a.mkdir(); b.mkdir()
    (a / 'x').write_bytes(b'x'); (b / 'x').mkdir()
    with pytest.raises(ValueError): sync_plan(a, b)


def test_big_endian_encoding_survives_edit(tmp_path):
    p = tmp_path / 'be.txt'
    p.write_bytes(codecs.BOM_UTF16_BE + '中文\r\n舊\r\n'.encode('utf-16-be'))
    doc = TextFile.load(p)
    doc.save('中文\n新\n')
    assert p.read_bytes() == codecs.BOM_UTF16_BE + '中文\r\n新\r\n'.encode('utf-16-be')


def test_unencodable_text_preserves_original(tmp_path):
    p = tmp_path / 'legacy.txt'; raw = '中文'.encode('cp950'); p.write_bytes(raw)
    doc = TextFile.load(p)
    with pytest.raises(UnicodeEncodeError): doc.save('😀')
    assert p.read_bytes() == raw


def test_empty_directory_is_compared_and_synced(tmp_path):
    a, b = tmp_path / 'a', tmp_path / 'b'
    (a / 'empty' / 'nested').mkdir(parents=True); b.mkdir()
    assert any(row.relative == 'empty/nested' for row in compare_paths(a, b))
    execute_plan(sync_plan(a, b))
    assert (b / 'empty' / 'nested').is_dir()


def test_copy_into_file_parent_rejected_before_writing(tmp_path):
    a, b = tmp_path / 'a', tmp_path / 'b'
    (a / 'folder').mkdir(parents=True); b.mkdir()
    (a / 'first').write_bytes(b'first')
    (a / 'folder' / 'nested').write_bytes(b'nested')
    (b / 'folder').write_bytes(b'keep')
    with pytest.raises(ValueError): sync_plan(a, b)
    assert not (b / 'first').exists()


def test_merge_save_preserves_untouched_mixed_newlines(tmp_path):
    p = tmp_path / 'mixed.txt'
    p.write_bytes(b'first\r\nsecond\nold\r\n')
    doc = TextFile.load(p)
    doc.save('first\nsecond\nnew\n')
    assert p.read_bytes() == b'first\r\nsecond\nnew\r\n'


def test_ascii_pdf_is_not_offered_as_text(tmp_path):
    p = tmp_path / 'file.pdf'; p.write_bytes(b'%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n')
    assert TextFile.load(p) is None


def test_copy_multiple_folders_keeps_sources_and_destination_extras(tmp_path):
    from core import selection_plan
    source, target = tmp_path / 'source', tmp_path / 'target'
    (source / 'one' / 'empty').mkdir(parents=True)
    (source / 'two').mkdir()
    (target / 'one').mkdir(parents=True)
    (source / 'one' / 'x').write_bytes(b'new')
    (source / 'two' / 'y').write_bytes(b'second')
    (target / 'one' / 'x').write_bytes(b'old')
    (target / 'one' / 'extra').write_bytes(b'keep')
    execute_plan(selection_plan([source / 'one', source / 'two'], target))
    assert (source / 'one' / 'x').read_bytes() == b'new'
    assert (source / 'two' / 'y').read_bytes() == b'second'
    assert (target / 'one' / 'x').read_bytes() == b'new'
    assert (target / 'two' / 'y').read_bytes() == b'second'
    assert (target / 'one' / 'empty').is_dir()
    assert (target / 'one' / 'extra').read_bytes() == b'keep'
