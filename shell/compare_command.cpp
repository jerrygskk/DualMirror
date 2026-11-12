#define UNICODE
#define _UNICODE
#include <windows.h>
#include <shobjidl.h>
#include <shlwapi.h>
#include <new>
#include "launch_common.h"
#include "selection.h"

// {77C7E3E9-12D8-4E73-A9D8-5EEB6D735ED9}
static const CLSID CLSID_Compare = {0xb711275a,0xf507,0x46d7,{0xb2,0xd3,0x00,0xca,0x2f,0x21,0xa8,0x03}};
static const CLSID CLSID_Select = {0x70ac930e,0x5504,0x42f5,{0x8f,0x61,0xb0,0xc0,0x8b,0x72,0xc3,0x7f}};
static HMODULE module;
static LONG objects = 0, locks = 0;

class CompareCommand final : public IExplorerCommand {
    LONG refs = 1;
    bool select;
    HRESULT Paths(IShellItemArray* items, std::wstring (&paths)[2], DWORD& count) {
        count = 0;
        if (!items || FAILED(items->GetCount(&count)) || count < 1 || count > 2) return E_INVALIDARG;
        for (DWORD i = 0; i < count; ++i) {
            IShellItem* item = nullptr;
            HRESULT result = items->GetItemAt(i, &item);
            if (FAILED(result)) return result;
            PWSTR path = nullptr;
            result = item->GetDisplayName(SIGDN_FILESYSPATH, &path); item->Release();
            if (FAILED(result)) return result;
            paths[i] = path; CoTaskMemFree(path);
        }
        return S_OK;
    }
public:
    CompareCommand(bool selection) : select(selection) { InterlockedIncrement(&objects); }
    ~CompareCommand() { InterlockedDecrement(&objects); }
    HRESULT STDMETHODCALLTYPE QueryInterface(REFIID iid, void** out) override {
        if (!out) return E_POINTER;
        *out = nullptr;
        if (iid == IID_IUnknown || iid == IID_IExplorerCommand) {
            *out = static_cast<IExplorerCommand*>(this); AddRef(); return S_OK;
        }
        return E_NOINTERFACE;
    }
    ULONG STDMETHODCALLTYPE AddRef() override { return InterlockedIncrement(&refs); }
    ULONG STDMETHODCALLTYPE Release() override {
        LONG result = InterlockedDecrement(&refs);
        if (!result) delete this;
        return result;
    }
    HRESULT STDMETHODCALLTYPE GetTitle(IShellItemArray* items, PWSTR* title) override {
        if (select) return SHStrDupW(L"選為左側比較", title);
        DWORD count = 0;
        if (items && SUCCEEDED(items->GetCount(&count)) && count == 1) {
            auto left = ReadText(DataPath(L"left.txt"));
            auto name = left.substr(left.find_last_of(L"\\/") + 1);
            if (name.size() > 64) name = name.substr(0, 61) + L"…";
            return SHStrDupW((L"與「" + name + L"」比較").c_str(), title);
        }
        return SHStrDupW(L"比較", title);
    }
    HRESULT STDMETHODCALLTYPE GetIcon(IShellItemArray*, PWSTR* icon) override {
        if (!icon) return E_POINTER;
        try { return SHStrDupW((ModuleDirectory(module) + L"\\Compare.ico").c_str(), icon); }
        catch (...) { *icon = nullptr; return E_OUTOFMEMORY; }
    }
    HRESULT STDMETHODCALLTYPE GetToolTip(IShellItemArray*, PWSTR* tip) override {
        return SHStrDupW(L"比較選取的兩個項目", tip);
    }
    HRESULT STDMETHODCALLTYPE GetCanonicalName(GUID* name) override {
        if (!name) return E_POINTER;
        *name = select ? CLSID_Select : CLSID_Compare; return S_OK;
    }
    HRESULT STDMETHODCALLTYPE GetState(IShellItemArray* items, BOOL, EXPCMDSTATE* state) override {
        if (!state) return E_POINTER;
        *state = ECS_HIDDEN;
        DWORD count = 0; std::wstring paths[2];
        if (FAILED(Paths(items, paths, count))) return S_OK;
        if (select) {
            if (count == 1 && GetFileAttributesW(paths[0].c_str()) != INVALID_FILE_ATTRIBUTES) *state = ECS_ENABLED;
        } else if (count == 2 ? SameKind(paths[0], paths[1]) : SameKind(ReadText(DataPath(L"left.txt")), paths[0]))
            *state = ECS_ENABLED;
        return S_OK;
    }
    HRESULT STDMETHODCALLTYPE Invoke(IShellItemArray* items, IBindCtx*) override {
        EXPCMDSTATE state;
        GetState(items, TRUE, &state);
        if (state != ECS_ENABLED) return E_INVALIDARG;
        std::wstring paths[2];
        try {
            DWORD count = 0;
            if (FAILED(Paths(items, paths, count))) return E_INVALIDARG;
            if (select) return SelectLeft(paths[0]);
            bool selected = count == 1;
            if (selected) { paths[1] = paths[0]; paths[0] = ReadText(DataPath(L"left.txt")); }
            if (!SameKind(paths[0], paths[1])) return E_INVALIDARG;
            const auto exe = ModuleDirectory(module) + L"\\CompareLauncher.exe";
            return Start(exe, Quote(exe) + (selected ? L" --selected " : L" ") + Quote(paths[0]) + L" " + Quote(paths[1]));
        } catch (...) { return E_OUTOFMEMORY; }
    }
    HRESULT STDMETHODCALLTYPE GetFlags(EXPCMDFLAGS* flags) override {
        if (!flags) return E_POINTER;
        *flags = ECF_DEFAULT; return S_OK;
    }
    HRESULT STDMETHODCALLTYPE EnumSubCommands(IEnumExplorerCommand** commands) override {
        if (!commands) return E_POINTER;
        *commands = nullptr; return E_NOTIMPL;
    }
};

class Factory final : public IClassFactory {
    LONG refs = 1;
    bool select;
public:
    Factory(bool selection) : select(selection) { InterlockedIncrement(&objects); }
    ~Factory() { InterlockedDecrement(&objects); }
    HRESULT STDMETHODCALLTYPE QueryInterface(REFIID iid, void** out) override {
        if (!out) return E_POINTER;
        *out = nullptr;
        if (iid == IID_IUnknown || iid == IID_IClassFactory) {
            *out = static_cast<IClassFactory*>(this); AddRef(); return S_OK;
        }
        return E_NOINTERFACE;
    }
    ULONG STDMETHODCALLTYPE AddRef() override { return InterlockedIncrement(&refs); }
    ULONG STDMETHODCALLTYPE Release() override {
        LONG result = InterlockedDecrement(&refs);
        if (!result) delete this;
        return result;
    }
    HRESULT STDMETHODCALLTYPE CreateInstance(IUnknown* outer, REFIID iid, void** out) override {
        if (!out) return E_POINTER;
        *out = nullptr;
        if (outer) return CLASS_E_NOAGGREGATION;
        auto object = new(std::nothrow) CompareCommand(select);
        if (!object) return E_OUTOFMEMORY;
        HRESULT result = object->QueryInterface(iid, out);
        object->Release(); return result;
    }
    HRESULT STDMETHODCALLTYPE LockServer(BOOL lock) override {
        if (lock) InterlockedIncrement(&locks); else InterlockedDecrement(&locks);
        return S_OK;
    }
};

extern "C" __declspec(dllexport) HRESULT WINAPI DllGetClassObject(REFCLSID clsid, REFIID iid, void** out) {
    if (!out) return E_POINTER;
    *out = nullptr;
    if (clsid != CLSID_Compare && clsid != CLSID_Select) return CLASS_E_CLASSNOTAVAILABLE;
    auto factory = new(std::nothrow) Factory(clsid == CLSID_Select);
    if (!factory) return E_OUTOFMEMORY;
    HRESULT result = factory->QueryInterface(iid, out);
    factory->Release(); return result;
}
extern "C" __declspec(dllexport) HRESULT WINAPI DllCanUnloadNow() {
    return objects == 0 && locks == 0 ? S_OK : S_FALSE;
}
BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) { module = instance; DisableThreadLibraryCalls(instance); }
    return TRUE;
}
