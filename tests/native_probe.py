"""在獨立程序測試真實 Windows Shell COM；僅讀寫呼叫者的暫存目錄。"""
import ctypes as c
from ctypes import wintypes as w
import json
import os
from pathlib import Path
import shutil
import sys
import time
import uuid
import subprocess

root = Path(__file__).resolve().parents[1]
temp = Path(sys.argv[1])
native = temp / 'native'; native.mkdir()
for name in ('FileCompareShell.dll', 'CompareLauncher.exe', 'Compare.ico'):
    shutil.copy2(root / 'shell' / name, native / name)
appdata = temp / 'appdata' / 'DualMirror'; appdata.mkdir(parents=True)
os.environ['LOCALAPPDATA'] = str(appdata.parent)
record = temp / 'record.json'
script = temp / 'record.py'
script.write_text('import json,sys\nfrom pathlib import Path\n' +
                  f'Path({str(record)!r}).write_text(json.dumps(sys.argv[1:], ensure_ascii=False),encoding="utf-8")\n', encoding='utf-8')
(appdata / 'launcher.txt').write_text(str(Path(sys.executable).with_name('pythonw.exe')) + '\n' + str(script), encoding='utf-8')

class GUID(c.Structure):
    _fields_ = [('a', w.DWORD), ('b', w.WORD), ('c', w.WORD), ('d', c.c_ubyte * 8)]
    def __init__(self, value):
        super().__init__()
        c.memmove(c.byref(self), uuid.UUID(value).bytes_le, 16)

def method(obj, index, *args):
    table = c.cast(obj, c.POINTER(c.POINTER(c.c_void_p))).contents
    return c.WINFUNCTYPE(c.c_long, c.c_void_p, *args)(table[index])

ole = c.OleDLL('ole32')
ole.CoInitializeEx(None, 2)
ole.CoTaskMemFree.argtypes = [c.c_void_p]
shell = c.OleDLL('shell32')
shell.SHParseDisplayName.argtypes = [w.LPCWSTR, c.c_void_p, c.POINTER(c.c_void_p), w.DWORD, c.POINTER(w.DWORD)]
shell.SHCreateShellItemArrayFromIDLists.argtypes = [w.UINT, c.POINTER(c.c_void_p), c.POINTER(c.c_void_p)]
library = c.WinDLL(str(native / 'FileCompareShell.dll'))
library.DllGetClassObject.argtypes = [c.POINTER(GUID), c.POINTER(GUID), c.POINTER(c.c_void_p)]
library.DllGetClassObject.restype = c.c_long
factory, command = c.c_void_p(), c.c_void_p()
clsid = GUID('B711275A-F507-46D7-B2D3-00CA2F21A803')
factory_iid = GUID('00000001-0000-0000-C000-000000000046')
command_iid = GUID('A08CE4D0-FA25-44AB-B57C-C7B1C323E0B9')
assert library.DllGetClassObject(c.byref(clsid), c.byref(factory_iid), c.byref(factory)) == 0
assert method(factory, 3, c.c_void_p, c.POINTER(GUID), c.POINTER(c.c_void_p))(factory, None, c.byref(command_iid), c.byref(command)) == 0
method(factory, 2)(factory)

select = c.c_void_p()
assert library.DllGetClassObject(c.byref(GUID('70AC930E-5504-42F5-8F61-B0C08B72C37F')), c.byref(factory_iid), c.byref(factory)) == 0
assert method(factory, 3, c.c_void_p, c.POINTER(GUID), c.POINTER(c.c_void_p))(factory, None, c.byref(command_iid), c.byref(select)) == 0
method(factory, 2)(factory)

def item_array(paths):
    pidls = (c.c_void_p * len(paths))()
    for index, path in enumerate(paths):
        address = c.cast(c.byref(pidls, index * c.sizeof(c.c_void_p)), c.POINTER(c.c_void_p))
        shell.SHParseDisplayName(str(path), None, address, 0, None)
    result = c.c_void_p()
    shell.SHCreateShellItemArrayFromIDLists(len(paths), pidls, c.byref(result))
    for pointer in pidls: ole.CoTaskMemFree(pointer)
    return result

files = [temp / name for name in ('第一份 space.txt', '第二份.txt', 'third.txt')]
for file in files: file.write_bytes(b'test')
folder = temp / 'folder'; folder.mkdir()
other = temp / 'other'; other.mkdir()
for paths, expected in ((files[:1], 2), (files[:2], 0), (files, 2), ([files[0], folder], 2), ([folder, other], 0)):
    array = item_array(paths)
    state = c.c_int(-1)
    assert method(command, 7, c.c_void_p, w.BOOL, c.POINTER(c.c_int))(command, array, True, c.byref(state)) == 0
    assert state.value == expected, (paths, state.value)
    method(array, 2)(array)
array = item_array(files[:2])
assert method(command, 8, c.c_void_p, c.c_void_p)(command, array, None) == 0
deadline = time.monotonic() + 15
while not record.exists() and time.monotonic() < deadline: time.sleep(.05)
assert record.exists(), 'native launcher did not deliver selection'
assert json.loads(record.read_text(encoding='utf-8')) == [str(file) for file in files[:2]]
method(array, 2)(array)

def state_of(obj, paths):
    array = item_array(paths); state = c.c_int(-1)
    assert method(obj, 7, c.c_void_p, w.BOOL, c.POINTER(c.c_int))(obj, array, True, c.byref(state)) == 0
    method(array, 2)(array)
    return state.value

def invoke(obj, paths):
    array = item_array(paths)
    result = method(obj, 8, c.c_void_p, c.c_void_p)(obj, array, None)
    method(array, 2)(array)
    return result

assert state_of(select, files[:1]) == 0
assert state_of(select, files[:2]) == 2
assert invoke(select, files[:1]) == 0
selected = appdata / 'left.txt'
assert selected.read_text(encoding='utf-8') == str(files[0])
assert state_of(command, [files[1]]) == 0
assert state_of(command, files[:1]) == 2
assert state_of(command, [folder]) == 2
array = item_array([files[1]]); title = c.c_void_p()
assert method(command, 3, c.c_void_p, c.POINTER(c.c_void_p))(command, array, c.byref(title)) == 0
assert files[0].name in c.wstring_at(title)
ole.CoTaskMemFree(title); method(array, 2)(array)
record.unlink()
assert invoke(command, [files[1]]) == 0
deadline = time.monotonic() + 15
while (not record.exists() or selected.exists()) and time.monotonic() < deadline: time.sleep(.05)
assert record.exists() and not selected.exists()
assert json.loads(record.read_text(encoding='utf-8')) == [str(files[0]), str(files[1])]
assert state_of(command, [files[1]]) == 2
assert invoke(select, [folder]) == 0
assert state_of(command, [other]) == 0
assert state_of(command, files[:1]) == 2
folder.rmdir()
assert state_of(command, [other]) == 2

# 無腳本欄位代表 EXE 啟動；以 Python EXE 與暫存腳本實際驗證傳參。
frozen_record = temp / 'frozen.json'
frozen_script = temp / '凍結 mode.py'
frozen_script.write_text('import json,sys\nfrom pathlib import Path\n' +
    f'Path({str(frozen_record)!r}).write_text(json.dumps(sys.argv[1:]),encoding="utf-8")\n', encoding='utf-8')
(appdata / 'launcher.txt').write_text(sys.executable + '\n\n', encoding='utf-8')
result = subprocess.run([str(native / 'CompareLauncher.exe'), str(frozen_script), str(files[1])], timeout=10)
assert result.returncode == 0
deadline = time.monotonic() + 10
while not frozen_record.exists() and time.monotonic() < deadline: time.sleep(.05)
assert json.loads(frozen_record.read_text(encoding='utf-8')) == [str(files[1])]

# 無法啟動時保留左側；自動關閉這次測試程序的錯誤框，避免留下視窗。
assert invoke(select, files[:1]) == 0
(appdata / 'launcher.txt').write_text(str(temp / 'missing.exe') + '\n\n', encoding='utf-8')
process = subprocess.Popen([str(native / 'CompareLauncher.exe'), '--selected', str(files[0]), str(files[1])])
user = c.WinDLL('user32')
callback_type = c.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)
user.GetWindowThreadProcessId.argtypes = [w.HWND, c.POINTER(w.DWORD)]
user.PostMessageW.argtypes = [w.HWND, w.UINT, w.WPARAM, w.LPARAM]
@callback_type
def close_error(hwnd, unused):
    pid = w.DWORD(); user.GetWindowThreadProcessId(hwnd, c.byref(pid))
    if pid.value == process.pid: user.PostMessageW(hwnd, 0x0010, 0, 0)
    return True
deadline = time.monotonic() + 10
try:
    while process.poll() is None and time.monotonic() < deadline:
        user.EnumWindows(close_error, 0); time.sleep(.05)
    assert process.wait(timeout=1) == 1
finally:
    if process.poll() is None: process.kill(); process.wait()
assert selected.read_text(encoding='utf-8') == str(files[0])
method(select, 2)(select)
method(command, 2)(command)
assert library.DllCanUnloadNow() == 0
ole.CoUninitialize()
print('Native COM selection and one-launch delivery passed')
