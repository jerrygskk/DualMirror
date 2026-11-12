#pragma once
#include <windows.h>
#include <string>

inline std::wstring Quote(const std::wstring& text) {
    std::wstring output = L"\"";
    size_t slashes = 0;
    for (wchar_t ch : text) {
        if (ch == L'\\') { ++slashes; continue; }
        if (ch == L'\"') { output.append(slashes * 2 + 1, L'\\'); output += ch; }
        else { output.append(slashes, L'\\'); output += ch; }
        slashes = 0;
    }
    output.append(slashes * 2, L'\\');
    return output + L"\"";
}

inline std::wstring ModuleDirectory(HMODULE module) {
    wchar_t path[32768];
    DWORD count = GetModuleFileNameW(module, path, 32768);
    if (!count || count >= 32768) return L"";
    std::wstring result(path, count);
    return result.substr(0, result.find_last_of(L"\\/"));
}

inline HRESULT Start(const std::wstring& exe, std::wstring command) {
    STARTUPINFOW si = {}; si.cb = sizeof(si);
    PROCESS_INFORMATION pi = {};
    if (!CreateProcessW(exe.c_str(), command.data(), nullptr, nullptr, FALSE,
                        CREATE_NO_WINDOW, nullptr, nullptr, &si, &pi))
        return HRESULT_FROM_WIN32(GetLastError());
    CloseHandle(pi.hThread); CloseHandle(pi.hProcess);
    return S_OK;
}
