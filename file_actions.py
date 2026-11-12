"""單側檔案操作；不提供永久刪除退路。"""
from pathlib import Path
import os
import re
import ctypes as C
import uuid


def identity(path):
    stat = Path(path).lstat()
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns


def unchanged(paths, expected):
    for path, stamp in zip(paths, expected):
        selected_paths(path.parent, [path])
        if identity(path) != stamp: raise RuntimeError(f'項目已變更，請重新整理：{path}')


def selected_paths(root, paths):
    root = Path(root).absolute()
    result = []
    for path in sorted(set(map(Path, paths)), key=lambda p: len(p.parts)):
        path = path.absolute()
        if path != root and not path.is_relative_to(root):
            raise ValueError('選取項目不在比較範圍內。')
        if not path.exists(): raise ValueError(f'項目不存在：{path}')
        for ancestor in (path, *path.parents):
            if ancestor.is_symlink() or ancestor.is_junction():
                raise ValueError('不支援操作連結或連結內的項目。')
            if ancestor == root: break
        if not any(path.is_relative_to(parent) for parent in result): result.append(path)
    return result


def rename_item(source, name):
    source = Path(source)
    if (not name or name in ('.', '..') or name[-1:] in (' ', '.')
            or re.search(r'[<>:"/\\|?*\x00-\x1f]', name)
            or re.fullmatch(r'(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?', name)):
        raise ValueError('名稱含 Windows 不允許的字元或保留名稱。')
    target = source.with_name(name)
    if target == source and target.name == source.name: return source
    if target.exists() and not os.path.samefile(source, target): raise FileExistsError('已有同名項目，未覆寫。')
    if source.is_symlink() or source.is_junction(): raise ValueError('不支援操作連結。')
    # Windows rename 不會覆寫已存在的目的檔案。
    source.rename(target)
    return target


def recycle_items(paths):
    """Windows IFileOperation：要求回收，失敗時停止，不改用永久刪除。"""
    from ctypes import wintypes as W
    ole = C.OleDLL('ole32'); shell = C.OleDLL('shell32')
    def guid(value): return (C.c_byte * 16).from_buffer_copy(uuid.UUID(value).bytes_le)
    def check(hr):
        if hr < 0: raise OSError(f'資源回收筒操作失敗（0x{hr & 0xffffffff:08X}）。')
    def call(obj, index, types, *args):
        table = C.cast(obj, C.POINTER(C.POINTER(C.c_void_p))).contents
        return C.WINFUNCTYPE(C.c_long, C.c_void_p, *types)(table[index])(obj, *args)
    check(ole.CoInitializeEx(None, 2))
    operation = C.c_void_p(); items = []
    try:
        check(ole.CoCreateInstance(guid('3ad05575-8857-4850-9277-11b85bdb8e09'), None, 1,
              guid('947aab5f-0a5c-4c13-b4d6-4bf7836fc9f8'), C.byref(operation)))
        check(call(operation, 5, [W.DWORD], 0x80000 | 0x100000 | 0x20000000 | 0x2454))
        shell.SHCreateItemFromParsingName.argtypes = [W.LPCWSTR, C.c_void_p, C.c_void_p, C.c_void_p]
        for path in paths:
            path = Path(path)
            if not path.exists(): raise FileNotFoundError(str(path))
            item = C.c_void_p()
            check(shell.SHCreateItemFromParsingName(str(path.absolute()), None,
                  guid('43826d1e-e718-42ee-bc55-a1e261c37bfe'), C.byref(item)))
            items.append(item)
            check(call(operation, 19, [C.c_void_p, C.c_void_p], item, None))
        check(call(operation, 21, []))
        aborted = W.BOOL()
        check(call(operation, 22, [C.POINTER(W.BOOL)], C.byref(aborted)))
        if aborted.value: raise OSError('操作未全部完成，請重新整理確認結果。')
    finally:
        for item in items: call(item, 2, [])
        if operation.value: call(operation, 2, [])
        ole.CoUninitialize()
