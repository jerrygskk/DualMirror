# 專案目錄整理實作計畫

> 執行方式：主程序依 executing-plans 與 test-driven-development 技能直接執行；依維護者後續指示，檢查通過後 commit，不推送。

## 目標與限制

依維護者已確認的目錄架構搬移檔案，保持現有功能、資料、版本及啟動方式。
根目錄 `main.py` 保留為單純啟動入口；維護者後續確認中文內容刪除指定句後，同意製作中英文 README。
不新增相依、不變更現有右鍵註冊或使用者設定。維護者後續要求 commit 完成後全新 build 一次，不進版、不推送。

## 搬移清單

- `core.py`、`binary_alignment.py`、`text_encoding.py`、`file_actions.py` → `lib/core/`。
- 主視窗與比較分頁、顯示及共用介面模組 → `lib/ui/`；主程式啟動函式 → `lib/application.py`。
- `shell_integration.py`、`single_instance.py` → `lib/integration/`。
- `app_settings.py`、`version.py` → `lib/settings/`。
- `DualMirror.spec` 與生成的版本資訊 → `packaging/`。
- `AppxManifest.xml` → `shell/`；註冊用資源複本仍保持 Windows 所需的目錄配置。
- `DEVELOPER.md`、`PITFALLS.md`、`HISTORY.md` → `docs/`。
- 圖示提案目錄 → `docs/design/`；舊實作計畫 → `docs/plans/`。

## 任務與驗證

- [x] 補目錄整理的回歸測試，確認尚未搬移時失敗。
- [x] 搬移程式並更新正式套件匯入；新增共用資源定位 `lib/paths.py`，支援原始碼與 frozen 資源。
- [x] 更新版本工具、打包宣告、Shell 資源來源與暫存複本測試，不保留舊模組相容轉接。
- [x] 搬移文件與設計資料，同步修正連結及啟動、測試與打包命令。
- [x] 語法檢查、完整測試與名稱／個資掃描；核對新頂層目錄未遭忽略。
- [x] Windows 可見視窗以暫存樣本驗證啟動、比較及第二程序請求，關閉所有試跑程序。
- [x] 一輪唯讀審查，只處理此次搬移造成的實際錯誤。
- [x] 經維護者確認刪除指定句，製作互相連結的中英文 README。
- [ ] 完成 commit 後，以正式 Python 與既有 spec 全新建置，並驗證 EXE 可見啟動。

## 主要風險

- 從其他工作目錄啟動時仍須找到圖示與 Shell 資源。
- onefile 解壓資源與原始碼目錄不同；以模擬 frozen 暫存目錄測試，不因此自行打包。
- Shell 固定資源複本的 manifest 必須在根層，原生 DLL 仍位於其 `shell/` 下。
- 版本工具只操作暫存專案複本；生成資料移到 `packaging/`，版號唯一來源仍只有一份。
- 所有 Python 匯入、測試猴子補丁目標及文件連結都須指向新位置。
