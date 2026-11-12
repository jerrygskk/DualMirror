#pragma once
#include "launch_common.h"

inline std::wstring DataPath(const wchar_t* name) {
    wchar_t path[32768] = {};
    DWORD count = GetEnvironmentVariableW(L"LOCALAPPDATA", path, 32768);
    if (!count || count >= 32768) return L"";
    return std::wstring(path) + L"\\DualMirror\\" + name;
}

inline std::wstring ReadText(const std::wstring& path) {
    HANDLE file = CreateFileW(path.c_str(), GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_DELETE,
                             nullptr, OPEN_EXISTING, 0, nullptr);
    if (file == INVALID_HANDLE_VALUE) return L"";
    DWORD size = GetFileSize(file, nullptr), read = 0;
    std::wstring text;
    if (size < 131072) {
        std::string raw(size, '\0');
        if (ReadFile(file, raw.data(), size, &read, nullptr) && read == size) {
            int count = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, raw.data(), size, nullptr, 0);
            if (count > 0) {
                text.resize(count);
                MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, raw.data(), size, text.data(), count);
            }
        }
    }
    CloseHandle(file); return text;
}

inline HRESULT SelectLeft(const std::wstring& value) {
    const auto path = DataPath(L"left.txt");
    auto folder = path.substr(0, path.find_last_of(L'\\'));
    if (!CreateDirectoryW(folder.c_str(), nullptr) && GetLastError() != ERROR_ALREADY_EXISTS)
        return HRESULT_FROM_WIN32(GetLastError());
    wchar_t temp[32768];
    if (!GetTempFileNameW(folder.c_str(), L"sel", 0, temp)) return HRESULT_FROM_WIN32(GetLastError());
    HANDLE file = CreateFileW(temp, GENERIC_WRITE, 0, nullptr, CREATE_ALWAYS, 0, nullptr);
    HRESULT result = E_FAIL;
    if (file != INVALID_HANDLE_VALUE) {
        int size = WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, value.data(), value.size(), nullptr, 0, nullptr, nullptr);
        std::string raw(size, '\0');
        WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, value.data(), value.size(), raw.data(), size, nullptr, nullptr);
        DWORD written = 0;
        if (size > 0 && WriteFile(file, raw.data(), size, &written, nullptr) && written == (DWORD)size) result = S_OK;
        CloseHandle(file);
    }
    if (SUCCEEDED(result) && !MoveFileExW(temp, path.c_str(), MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH))
        result = HRESULT_FROM_WIN32(GetLastError());
    DeleteFileW(temp); return result;
}

inline bool SameKind(const std::wstring& left, const std::wstring& right) {
    DWORD a = GetFileAttributesW(left.c_str()), b = GetFileAttributesW(right.c_str());
    return !left.empty() && !right.empty() && _wcsicmp(left.c_str(), right.c_str()) &&
        a != INVALID_FILE_ATTRIBUTES && b != INVALID_FILE_ATTRIBUTES &&
        (a & FILE_ATTRIBUTE_DIRECTORY) == (b & FILE_ATTRIBUTE_DIRECTORY);
}
