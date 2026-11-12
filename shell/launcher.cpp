#include "selection.h"
#include <shellapi.h>

int WINAPI wWinMain(HINSTANCE, HINSTANCE, PWSTR, int) {
    auto settings = ReadText(DataPath(L"launcher.txt"));
    auto split = settings.find(L'\n');
    auto exe = settings.substr(0, split);
    auto script = split == std::wstring::npos ? L"" : settings.substr(split + 1);
    while (!exe.empty() && (exe.back() == L'\r' || exe.back() == L'\n')) exe.pop_back();
    while (!script.empty() && (script.back() == L'\r' || script.back() == L'\n')) script.pop_back();
    int count = 0;
    auto args = CommandLineToArgvW(GetCommandLineW(), &count);
    bool selected = count == 4 && !wcscmp(args[1], L"--selected");
    int first = selected ? 2 : 1;
    HRESULT result = E_INVALIDARG;
    if (!exe.empty() && split != std::wstring::npos && count - first == 2 && SameKind(args[first], args[first + 1])) {
        std::wstring command = Quote(exe);
        if (!script.empty()) command += L" " + Quote(script);
        command += L" " + Quote(args[first]) + L" " + Quote(args[first + 1]);
        result = Start(exe, command);
        // 只清掉本次比較使用的左側，不刪除稍後重新指定的選取。
        if (SUCCEEDED(result) && (!selected || ReadText(DataPath(L"left.txt")) == args[first]))
            DeleteFileW(DataPath(L"left.txt").c_str());
    }
    LocalFree(args);
    if (FAILED(result)) MessageBoxW(nullptr, L"無法啟動比較，請確認檔案仍存在，並重新啟用右鍵整合。", L"DualMirror／雙鏡", MB_OK | MB_ICONERROR);
    return FAILED(result) ? 1 : 0;
}
