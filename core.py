"""檔案比較與寫入；不依賴介面，所有路徑均為本機檔案系統路徑。"""
from dataclasses import dataclass, replace
from pathlib import Path
import codecs
import difflib
import hashlib
import os
import shutil
import tempfile


def fingerprint(path):
    path = Path(path)
    if path.is_symlink() or path.is_junction():
        raise ValueError(f'不支援連結：{path}')
    if not path.exists():
        return None
    if path.is_dir():
        return b'DIRECTORY'
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.digest()


def pair_stamp(left, right):
    def stamp(path):
        try: stat = Path(path).stat()
        except FileNotFoundError: return None
        return stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns, stat.st_ino
    return stamp(left), stamp(right)


def atomic_write(path, data, expected):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.compare-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if fingerprint(path) != expected:
            raise RuntimeError(f'檔案已變更，請重新比較：{path}')
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


@dataclass
class TextFile:
    path: Path
    text: str
    encoding: str
    newline: str
    original: bytes

    @classmethod
    def load(cls, path, encoding=None):
        path = Path(path)
        if path.is_symlink() or path.is_junction():
            raise ValueError(f'不支援連結：{path}')
        with path.open('rb') as stream:
            header = stream.read(4096)
            if header.startswith((b'%PDF-', b'PK\x03\x04', b'\x89PNG', b'\xff\xd8\xff', b'GIF87a', b'GIF89a', b'\xd0\xcf\x11\xe0', b'MZ')):
                return None
            raw = header + stream.read()
        return cls.from_bytes(path, raw, encoding)

    @classmethod
    def from_bytes(cls, path, raw, encoding=None):
        from text_encoding import decode_text
        result = decode_text(raw, encoding)
        if result is None: return None
        text, encoding = result
        newline = '\r\n' if '\r\n' in text else ('\r' if '\r' in text else '\n')
        return cls(Path(path), text.replace('\r\n', '\n').replace('\r', '\n'), encoding, newline, raw)

    def encoded(self, text):
        # 未修改時保留原始位元組（包含混合換行）。
        if text == self.text:
            raw = self.original
        else:
            old_lines = self.text.splitlines(True)
            original_lines = self.original.decode(self.encoding).splitlines(True)
            new_lines = text.splitlines(True)
            chunks = []
            for tag, a, b, c, d in difflib.SequenceMatcher(None, old_lines, new_lines, autojunk=False).get_opcodes():
                chunks.extend(original_lines[a:b] if tag == 'equal' else [line.replace('\n', self.newline) for line in new_lines[c:d]])
            normalized = ''.join(chunks)
            if self.encoding in ('utf-16', 'utf-32'):
                width = 2 if self.encoding == 'utf-16' else 4
                big = self.original.startswith(codecs.BOM_UTF16_BE if width == 2 else codecs.BOM_UTF32_BE)
                raw = self.original[:width] + normalized.encode(f'{self.encoding}-{"be" if big else "le"}')
            else:
                raw = normalized.encode(self.encoding)
        return raw

    def save(self, text):
        raw = self.encoded(text)
        atomic_write(self.path, raw, hashlib.sha256(self.original).digest())
        self.original, self.text = raw, text


def differences(left, right):
    return [item for item in difflib.SequenceMatcher(lambda line: not line.strip(), left.splitlines(True), right.splitlines(True), autojunk=False).get_opcodes() if item[0] != 'equal']


def merge_block(left, right, block, destination):
    _, a, b, c, d = block
    llines, rlines = left.splitlines(True), right.splitlines(True)
    if destination == 'right':
        rlines[c:d] = llines[a:b]
        return ''.join(rlines)
    llines[a:b] = rlines[c:d]
    return ''.join(llines)


@dataclass
class Entry:
    relative: str
    left: Path
    right: Path
    left_size: int | None
    right_size: int | None
    status: str
    directory: bool = False
    verified: bool = False
    stamp: tuple = ()


def inventory(root):
    found = {}
    def visit(folder):
        for path in sorted(folder.iterdir()):
            if path.is_symlink() or path.is_junction():
                raise ValueError(f'不支援連結：{path}')
            if path.is_dir():
                found[path.relative_to(root).as_posix()] = path
                visit(path)
            else:
                found[path.relative_to(root).as_posix()] = path
    visit(root)
    return found


def roots(left, right):
    left, right = Path(left).resolve(), Path(right).resolve()
    if left == right or left in right.parents or right in left.parents:
        raise ValueError('左右路徑不得相同或互相包含。')
    if not left.exists() or not right.exists():
        raise ValueError('請選擇兩個存在的檔案或資料夾。')
    if left.is_dir() != right.is_dir():
        raise ValueError('左右必須同為檔案或同為資料夾。')
    return left, right


def compare_paths(left, right, detailed=False):
    left, right = roots(left, right)
    if left.is_dir():
        lmap, rmap = inventory(left), inventory(right)
    else:
        lmap, rmap = {'': left}, {'': right}
    rows = []
    for name in sorted(lmap.keys() | rmap.keys(), key=str.casefold):
        lp, rp = lmap.get(name), rmap.get(name)
        ld, rd = lp is not None and lp.is_dir(), rp is not None and rp.is_dir()
        if ld and rd:
            status = 'same'
        elif (ld and rp is not None) or (rd and lp is not None):
            status = 'conflict'
        elif ld or rd:
            status = 'left' if ld else 'right'
        elif lp is None:
            status = 'right'
        elif rp is None:
            status = 'left'
        else:
            ls, rs = lp.stat(), rp.stat()
            status = 'same' if (ls.st_size, ls.st_mtime_ns) == (rs.st_size, rs.st_mtime_ns) else 'different'
        rows.append(Entry(name or left.name, lp or left / name, rp or right / name,
                          lp.stat().st_size if lp and not ld else None,
                          rp.stat().st_size if rp and not rd else None, status, bool(ld or rd),
                          stamp=pair_stamp(lp or left / name, rp or right / name)))
    return verify_contents(rows) if detailed else rows


def verify_contents(rows, selected=None, method='binary', rules=()):
    """詳細驗證選取檔案及選取資料夾的子項目；None 表示全部。"""
    result = []
    for row in rows:
        chosen = selected is None or row.relative in selected or any(row.relative.startswith(name + '/') for name in selected)
        if not chosen or row.directory or row.status not in ('same', 'different'):
            result.append(row)
            continue
        for path in (row.left, row.right):
            if path.is_symlink() or path.is_junction(): raise ValueError(f'不支援連結：{path}')
        before = [path.stat() for path in (row.left, row.right)]
        equal = before[0].st_size == before[1].st_size
        if method == 'rules':
            documents = [TextFile.load(path) for path in (row.left, row.right)]
            if all(doc is not None for doc in documents):
                def normalize(text):
                    if 'newlines' in rules: text = text.replace('\r\n', '\n').replace('\r', '\n')
                    if 'space' in rules: text = ''.join(text.split())
                    if 'case' in rules: text = text.casefold()
                    return text
                equal = normalize(documents[0].text) == normalize(documents[1].text)
            else:
                equal = verify_contents([row])[0].status == 'same'
        elif method == 'crc':
            import zlib
            def checksum(path):
                value = 0
                with path.open('rb') as stream:
                    while chunk := stream.read(1024 * 1024): value = zlib.crc32(chunk, value)
                return value
            equal = equal and checksum(row.left) == checksum(row.right)
        elif method != 'binary':
            raise ValueError('未知的比較方式。')
        elif equal:
            with row.left.open('rb') as left, row.right.open('rb') as right:
                while True:
                    ldata, rdata = left.read(1024 * 1024), right.read(1024 * 1024)
                    if ldata != rdata:
                        equal = False
                        break
                    if not ldata: break
        after = [path.stat() for path in (row.left, row.right)]
        stamp = lambda stat: (stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns, stat.st_ino)
        if any(stamp(a) != stamp(b) for a, b in zip(before, after)):
            raise RuntimeError(f'檔案在比較期間變更，請重新檢查：{row.relative}')
        result.append(replace(row, status='same' if equal else 'different', verified=True,
                              left_size=after[0].st_size, right_size=after[1].st_size,
                              stamp=tuple(stamp(stat) for stat in after)))
    return result


@dataclass
class CopyAction:
    source: Path
    target: Path
    source_hash: bytes
    target_hash: bytes | None
    directory: bool = False


def make_action(source, target):
    source, target = Path(source), Path(target)
    for path in (source, target):
        for parent in (path, *path.parents):
            if parent.is_symlink() or parent.is_junction():
                raise ValueError(f'不支援連結：{parent}')
    if target.is_dir() and not source.is_dir():
        raise ValueError(f'目的端是資料夾，無法覆寫：{target}')
    if source.is_dir() and target.exists() and not target.is_dir():
        raise ValueError(f'目的端是檔案，無法建立資料夾：{target}')
    return CopyAction(source, target, fingerprint(source), fingerprint(target), source.is_dir())


def sync_plan(source, target):
    rows = compare_paths(source, target, detailed=True)
    if any(row.status == 'conflict' for row in rows):
        raise ValueError('有檔案與資料夾同名衝突，請先處理後再同步。')
    return [make_action(row.left, row.right) for row in rows if row.status in ('left', 'different')]


def copy_checked(action):
    if fingerprint(action.source) != action.source_hash:
        raise RuntimeError(f'來源已變更，請重新比較：{action.source}')
    for path in (action.source, action.target):
        for parent in (path, *path.parents):
            if parent.is_symlink() or parent.is_junction():
                raise ValueError(f'路徑已變成連結：{parent}')
    action.target.parent.mkdir(parents=True, exist_ok=True)
    if action.directory:
        current = fingerprint(action.target)
        # 父資料夾可能已由先前動作建立，不覆寫既有內容。
        if current not in (None, b'DIRECTORY'):
            raise RuntimeError(f'目的端已變更，請重新比較：{action.target}')
        action.target.mkdir(exist_ok=True)
        return
    fd, name = tempfile.mkstemp(prefix='.compare-', dir=action.target.parent)
    os.close(fd)
    try:
        shutil.copy2(action.source, name)
        if fingerprint(name) != action.source_hash or fingerprint(action.source) != action.source_hash:
            raise RuntimeError(f'來源已變更，請重新比較：{action.source}')
        if fingerprint(action.target) != action.target_hash:
            raise RuntimeError(f'目的端已變更，請重新比較：{action.target}')
        os.replace(name, action.target)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def execute_plan(plan):
    # 全部預檢後才寫入；執行中仍逐檔再次確認。
    for action in plan:
        if fingerprint(action.source) != action.source_hash or fingerprint(action.target) != action.target_hash:
            raise RuntimeError('檔案已變更，請重新比較。')
    for index, action in enumerate(plan):
        try:
            copy_checked(action)
        except Exception as error:
            raise RuntimeError(f'已完成 {index}／{len(plan)} 個檔案，其餘未執行。\n{error}') from error
    return len(plan)


def selection_plan(sources, target):
    """將多個選取項目複製到指定資料夾；保留來源與目的端額外檔案。"""
    target = Path(target)
    if not target.is_dir():
        raise ValueError('目的地必須是存在的資料夾。')
    selected = sorted({Path(path) for path in sources}, key=lambda p: len(p.parts))
    roots_to_copy = []
    for source in selected:
        if any(parent == source or parent in source.parents for parent in roots_to_copy): continue
        if not source.exists(): raise ValueError(f'來源不存在：{source}')
        destination = target / source.name
        real_source, real_destination = source.resolve(), destination.resolve()
        if real_source == real_destination or real_source in real_destination.parents:
            raise ValueError('不能複製到來源本身或其子資料夾。')
        roots_to_copy.append(source)
    actions = {}
    for source in roots_to_copy:
        content = {'': source}
        if source.is_dir(): content.update(inventory(source))
        for relative, path in content.items():
            destination = target / source.name / relative if relative else target / source.name
            if destination in actions and actions[destination].source != path:
                raise ValueError(f'多個來源將寫入同一路徑，請分批處理：{destination}')
            action = make_action(path, destination)
            if action.source_hash != action.target_hash: actions[destination] = action
    return list(actions.values())
