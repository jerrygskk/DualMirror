"""文字編碼選單、保守偵測與嚴格解碼；不以替代字元吞掉錯誤。"""
import codecs
from charset_normalizer import from_bytes


ENCODINGS = [
    ('UTF-8', 'utf-8'), ('UTF-8（BOM）', 'utf-8-sig'),
    ('UTF-16（BOM）', 'utf-16'), ('UTF-16 LE', 'utf-16-le'), ('UTF-16 BE', 'utf-16-be'),
    ('UTF-32（BOM）', 'utf-32'), ('UTF-32 LE', 'utf-32-le'), ('UTF-32 BE', 'utf-32-be'),
    ('繁體中文（Big5／CP950）', 'cp950'), ('簡體中文（GB18030）', 'gb18030'),
    ('日文（Shift-JIS／CP932）', 'cp932'), ('日文（EUC-JP）', 'euc_jp'),
    ('韓文（CP949）', 'cp949'), ('西歐（Windows-1252）', 'cp1252'),
    ('斯拉夫語（Windows-1251）', 'cp1251'), ('中歐（Windows-1250）', 'cp1250'),
    ('希臘文（Windows-1253）', 'cp1253'), ('土耳其文（Windows-1254）', 'cp1254'),
    ('希伯來文（Windows-1255）', 'cp1255'), ('阿拉伯文（Windows-1256）', 'cp1256'),
    ('泰文（Windows-874）', 'cp874'), ('西歐（ISO-8859-1）', 'iso8859-1'),
    ('DOS（CP437）', 'cp437'), ('DOS 西歐（CP850）', 'cp850'),
    ('系統 ANSI', 'mbcs'), ('系統 DOS／OEM', 'oem'),
]


def bom_encoding(raw):
    for mark, encoding in ((codecs.BOM_UTF32_LE, 'utf-32'), (codecs.BOM_UTF32_BE, 'utf-32'),
                           (codecs.BOM_UTF16_LE, 'utf-16'), (codecs.BOM_UTF16_BE, 'utf-16'),
                           (codecs.BOM_UTF8, 'utf-8-sig')):
        if raw.startswith(mark): return encoding
    return None


def decode_text(raw, encoding=None):
    bom = bom_encoding(raw)
    if encoding:
        name = codecs.lookup(encoding).name
        if bom and (name == bom or (bom == 'utf-8-sig' and name == 'utf-8')
                    or (bom in ('utf-16', 'utf-32') and name.startswith(bom))):
            if name.endswith(('-le', '-be')):
                width = 2 if bom == 'utf-16' else 4
                actual = 'le' if raw.startswith(codecs.BOM_UTF16_LE if width == 2 else codecs.BOM_UTF32_LE) else 'be'
                if not name.endswith(actual): raise UnicodeError('選取的位元組順序與 BOM 不一致。')
            encoding = bom
        text = raw.decode(encoding)
    else:
        encoding = bom
        if encoding is None:
            try:
                text = raw.decode('utf-8')
                if '\0' not in text: encoding = 'utf-8'
            except UnicodeError:
                pass
        if encoding is None:
            if b'\0' in raw:
                # Only attempt BOM-less Unicode for a substantial, regular
                # zero-byte pattern; short binary files must remain binary.
                if len(raw) < 16: return None
                if len(raw) % 4 == 0 and any(all(b == 0 for b in raw[i::4]) for i in (0, 3)):
                    candidates = ['utf-32-le', 'utf-32-be']
                elif len(raw) % 2 == 0 and max(raw[::2].count(0), raw[1::2].count(0)) >= len(raw) // 4:
                    candidates = ['utf-16-le', 'utf-16-be']
                else: return None
                matches = from_bytes(raw, cp_isolation=candidates)
            else:
                matches = from_bytes(raw)
            match = matches.best()
            if match is None: return None
            encoding = {'ascii': 'utf-8', 'big5': 'cp950', 'big5hkscs': 'cp950'}.get(match.encoding, match.encoding)
        try: text = raw.decode(encoding)
        except UnicodeError: return None
    if any(ord(c) < 32 and c not in '\t\n\r\f' for c in text): return None
    return text, encoding


def encoding_label(doc):
    name = doc.encoding
    if name in ('utf-16', 'utf-32'):
        width = 2 if name == 'utf-16' else 4
        big = doc.original.startswith(codecs.BOM_UTF16_BE if width == 2 else codecs.BOM_UTF32_BE)
        return f'{name.upper()} {"BE" if big else "LE"}（BOM）'
    return next((label for label, codec in ENCODINGS if codec == name), name.upper())
