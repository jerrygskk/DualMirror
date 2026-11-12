import codecs
import pytest
from lib.core.core import TextFile
from lib.ui.text_compare import TextCompare
from PySide6.QtGui import QTextCursor, QInputMethodEvent
from PySide6.QtWidgets import QApplication


LANGUAGE_CASES = [
    ('text', '.txt', 'plain text\n'),
    ('python', '.py', 'def hello():\n    return "中文"\n'),
    ('c', '.c', '#include <stdio.h>\nint main() { return 0; }\n'),
    ('cpp', '.cpp', '// comment\nclass Sample {};\n'),
    ('csharp', '.cs', 'using System;\nclass Demo {}\n'),
    ('java', '.java', 'public class Demo {}\n'),
    ('javascript', '.js', 'const value = "中文";\n'),
    ('typescript', '.ts', 'const value: number = 1;\n'),
    ('html', '.html', '<!DOCTYPE html><p>中文</p>\n'),
    ('css', '.css', 'body { color: red; }\n'),
    ('json', '.json', '{"name": "中文", "count": 1}\n'),
    ('xml', '.xml', '<?xml version="1.0"?><root>中文</root>\n'),
    ('yaml', '.yaml', 'name: "中文"\nitems:\n  - one\n'),
    ('sql', '.sql', 'SELECT name FROM items WHERE id = 1;\n'),
    ('ini', '.ini', '[config]\nname=value\n'),
    ('bash', '.sh', '#!/bin/bash\nprintf "%s" "$HOME"\n'),
    ('powershell', '.ps1', 'Write-Host "中文"\n'),
    ('bat', '.cmd', '@echo off\nset value=1\n'),
    ('markdown', '.md', '# 標題\n**text**\n'),
]


@pytest.mark.parametrize('alias,suffix,text', LANGUAGE_CASES, ids=[row[0] for row in LANGUAGE_CASES])
def test_every_language_detects_switches_and_colors_without_changing_bytes(qtbot, tmp_path, alias, suffix, text):
    left, right = tmp_path / ('left' + suffix), tmp_path / ('right' + suffix)
    raw = text.replace('\n', '\r\n').encode('utf-8')
    for path in (left, right): path.write_bytes(raw)
    window = TextCompare(left, right); qtbot.addWidget(window)
    assert window.syntax_highlighters[0].language == alias
    for side in (0, 1):
        box = window.language_boxes[side]
        box.setCurrentIndex(box.findData('text'))
        assert window.syntax_highlighters[side].language == 'text'
        box.setCurrentIndex(box.findData(alias))
        editor = (window.left_edit, window.right_edit)[side]
        block = editor.document().firstBlock()
        colors = []
        while block.isValid():
            colors.extend(item.format.foreground().color().name() for item in block.layout().formats())
            block = block.next()
        if alias != 'text': assert any(color != '#111111' for color in colors)
        assert window.texts[side] == text
        assert window.docs[side].encoded(text) == raw
        editor.moveCursor(QTextCursor.End)
        qtbot.keyClicks(editor, 'X')
        window.flush_edit()
        assert window.texts[side] == text + 'X'
        preedit = QInputMethodEvent('中', [])
        QApplication.sendEvent(editor, preedit)
        assert window.texts[side] == text + 'X'
        event = QInputMethodEvent(); event.setCommitString('中')
        QApplication.sendEvent(editor, event)
        window.flush_edit()
        assert window.texts[side] == text + 'X中'
        window.undo(); window.undo()
        assert window.texts[side] == text and not any(window.dirty)
    window.close()


def test_language_menu_is_exactly_the_languages_exercised(qtbot, tmp_path):
    from lib.ui.syntax_styles import LANGUAGES
    assert {row[0] for row in LANGUAGES} == {row[0] for row in LANGUAGE_CASES}


@pytest.mark.parametrize('encoding,text', [
    ('utf-8', '中文\r\n'), ('utf-8-sig', '中文\r\n'),
    ('utf-16', '中文\r\n'), ('utf-16-le', '中文\r\n'), ('utf-16-be', '中文\r\n'),
    ('utf-32', '中文\r\n'), ('utf-32-le', '中文\r\n'), ('utf-32-be', '中文\r\n'),
    ('cp950', '繁體中文測試\r\n'), ('gb18030', '简体中文测试\r\n'),
    ('cp932', '日本語テスト\r\n'), ('euc_jp', '日本語テスト\r\n'),
    ('cp949', '한국어 테스트\r\n'), ('cp1252', 'café\r\n'),
    ('cp1251', 'Привет\r\n'), ('cp1250', 'Příliš\r\n'),
    ('cp1253', 'Ελληνικά\r\n'), ('cp1254', 'Türkçe\r\n'),
    ('cp1255', 'שלום\r\n'), ('cp1256', 'مرحبا\r\n'),
    ('cp874', 'ภาษาไทย\r\n'), ('iso8859-1', 'café\r\n'),
    ('cp437', 'café\r\n'), ('cp850', 'café\r\n'),
    ('mbcs', 'sample\r\n'), ('oem', 'sample\r\n'),
], ids=lambda item: item if '\r' not in item else 'text')
def test_explicit_encoding_round_trip(tmp_path, encoding, text):
    raw = text.encode(encoding)
    path = tmp_path / 'sample'; path.write_bytes(raw)
    doc = TextFile.load(path, encoding=encoding)
    assert doc.text == text.replace('\r\n', '\n')
    assert doc.encoded(doc.text) == raw
    doc.save(doc.text + 'X')
    assert path.read_bytes().decode(encoding).endswith('\r\nX')


def test_manual_decode_blocks_unsaved_edits_and_keeps_original_bytes(qtbot, tmp_path, monkeypatch):
    import lib.ui.text_compare as text_compare
    messages = []
    monkeypatch.setattr(text_compare, 'msgInfo', lambda *args: messages.append(args))
    monkeypatch.setattr(text_compare, 'confirmBox', lambda *a, **k: True)
    raw = b'caf\xe9\r\n'
    left, right = tmp_path / 'left', tmp_path / 'right'
    for path in (left, right): path.write_bytes(raw)
    window = TextCompare(left, right); qtbot.addWidget(window)
    box = window.encoding_boxes[0]
    box.setCurrentIndex(box.findData('cp1252'))
    assert window.texts[0] == 'café\n'
    window.commit_text(1, 'modified\n')
    box.setCurrentIndex(box.findData('iso8859-1'))
    assert box.currentData() == 'cp1252'
    assert window.texts[1] == 'modified\n' and messages
    assert left.read_bytes() == right.read_bytes() == raw
    window.texts = [doc.text for doc in window.docs]; window.close()


@pytest.mark.parametrize('encoding,text', [
    ('cp950', '這是一段繁體中文文字，測試檔案比較與編碼偵測。' * 5),
    ('gb18030', '这是一段简体中文文本，测试文件比较与编码检测。' * 5),
    ('cp932', 'これは日本語の文章です。文字コードを確認します。' * 5),
    ('euc_jp', 'これは日本語の文章です。文字コードを確認します。' * 5),
    ('cp949', '이것은 한국어 문장입니다. 파일 인코딩을 확인합니다.' * 5),
    ('utf-16-le', 'A sample without a byte order mark.\r\n'),
    ('utf-16-be', 'A sample without a byte order mark.\r\n'),
    ('utf-32-le', 'A sample without a byte order mark.\r\n'),
    ('utf-32-be', 'A sample without a byte order mark.\r\n'),
], ids=lambda item: item if len(item) < 20 else 'sample')
def test_automatic_multilingual_encoding_detection(tmp_path, encoding, text):
    path = tmp_path / 'sample'
    raw = text.encode(encoding); path.write_bytes(raw)
    doc = TextFile.load(path)
    assert doc is not None and doc.text == text.replace('\r\n', '\n')
    assert doc.encoded(doc.text) == raw


def test_invalid_manual_decode_restores_selection_without_changing_text(qtbot, tmp_path, monkeypatch):
    import lib.ui.text_compare as text_compare
    errors = []
    monkeypatch.setattr(text_compare, 'msgCritical', lambda *a: errors.append(a))
    left, right = tmp_path / 'left', tmp_path / 'right'
    for path in (left, right): path.write_bytes(b'caf\xe9\n')
    window = TextCompare(left, right); qtbot.addWidget(window)
    before = list(window.texts)
    box = window.encoding_boxes[0]
    box.setCurrentIndex(box.findData('utf-8'))
    assert errors and box.currentData() is None
    assert window.texts == before and not any(window.dirty)
    window.close()
