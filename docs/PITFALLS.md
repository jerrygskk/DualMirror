# DualMirror 踩雷表

只記本專案已確認的症狀、原因與處理；完整架構及操作看 [DEVELOPER.md](DEVELOPER.md)。

| 編號 | 症狀／原因 | 處理與驗證位置 |
| --- | --- | --- |
| TXT-1 | Qt 顯示文字會正規化 NBSP 等字元；把 `toPlainText()` 存回去會改掉原始資料。 | 原文獨立保存於 `self.texts`，經 UTF-16 位置映射套用局部編輯；`tests/test_text_editing.py`、`tests/test_ui.py`。 |
| TXT-2 | 對齊補行屬於畫面，不是真實文字；直接刪除或打字會讓資料與顯示不同步。 | 補行輸入建立真實文字行，刪純補行不改原文；下一事件重建對齊。測試同上。 |
| TXT-3 | IME 組字格式更新也會回報整段移除／加入；將通知範圍直接寫回，會誤存顯示補位換行，連打 `11` 後換行或游標跳動。 | 比較 Qt 正規化快照，只映射通知範圍內真正變動的文字；提交保留實際插入位置，避免重複字元誤定位。原文不取自完整 `toPlainText()`；`tests/test_text_editing.py` 驗證數字、中文、非 BMP 與 CRLF。 |
| TXT-4 | Consolas 空白／英文列與中文回退字型高度不同，部分合併後左右逐行錯位；分別置中也可能產生不同起始列。 | `AlignedDocumentLayout` 共用兩側相同行高，明確跳轉後同步捲動；保留 layout 強參照，字型重算計時器歸視窗所有，避免已銷毀 Editor 仍被回呼。`tests/test_merge_alignment.py`。 |
| TXT-5 | 長段相同空白可能成為配對錨點，擠掉中間相同文字，造成不合理的大區塊。 | SequenceMatcher 優先相同非空白行，空白仍比較並保留於資料；`tests/test_merge_alignment.py`。空白仍參與比較；重複文字可能存在其他有效配對。 |
| TXT-6 | 每行各自畫斜線會重設圖樣起點，補位區間出現橫向接縫。 | 在 viewport 連續繪製整個補位區間，保留選取／游標；Qt 圖樣週期以裝置像素核對。`tests/test_text_difference_style.py`。 |
| TXT-7 | 合併後直接呼叫差異跳轉及 `centerCursor()`，即使只複製一行也會把畫面帶走。 | 合併保留來源側檢視錨點及水平位置，抑制刷新中的交互捲動，結束後左右同位；上一段／下一段仍可跳轉。`tests/test_merge_alignment.py`。 |
| TXT-8 | 語法上色座標若直接套到對齊文字，會被補位與 UTF-16／非 BMP 差異帶歪；格式通知也不能當作輸入。 | `lib/ui/syntax_styles.py` 以完整原文分詞，再經原始位置映射上色；不改字型或原文，差異標示優先。`tests/test_language_encoding.py` 逐項涵蓋 19 種樣式、鍵盤／IME 輸入與復原。 |
| ENC-1 | 自動編碼偵測有歧義；帶 BOM 的位元組順序、無 BOM Unicode 與二進位判斷不能混為一談。 | `lib/core/text_encoding.py` 優先 BOM／UTF-8，無 BOM 零位元組採保守限制，再用 charset-normalizer；保留手動選擇，解碼失敗不替代。任一側未儲存時不切換；26 種明確編碼讀寫及多語言偵測見 `tests/test_language_encoding.py`。 |
| IO-1 | 預覽後檔案仍可被其他程式修改，直接覆寫可能遺失變更。 | 區塊操作及儲存核對兩端；另存確認後再核對目的快照，暫存寫完才原子替換；`lib/core/core.py` 與編輯測試。 |
| IO-2 | 大小／時間相同不能證明內容相同；檔案變動後沿用舊驗證結果會誤顯示相同。 | 只有內容檢查後顯示符號，變動通知使相關結果失效；`tests/test_binary_results.py`。 |
| UI-1 | 比較符號放在左表格最後一欄，會跟著欄寬與水平捲動走。 | 改用獨立 QSplitterHandle 窄區，依可見列定位；`tests/test_result_gutter.py`，已做可見視窗拖曳及捲動試跑。 |
| UI-2 | 全域下拉樣式曾造成箭頭消失。 | `assets/icons/comboArrow.svg` 明確供應箭頭；`tests/test_combo_arrow.py`。 |
| UI-3 | 選單式下拉從原欄位展開，蓋住箭頭，且跳過 Qt 的下拉動畫。 | 共用比較樣式指定 `combobox-popup: 0`，清單由欄位下緣展開、沿用內建動畫；`tests/test_filter_popup.py` 及 Windows 可見視窗驗證。 |
| UI-4 | 中央上移按鈕停用後，滑鼠事件會傳至父 QSplitterHandle，按鈕區出現左右拖曳游標且可拖動。 | 以啟用的外層容器承接事件，一般箭頭游標；下方結果分隔區繼續可拖曳。`tests/test_path_navigation.py` 及可見視窗試跑。 |
| UI-5 | 用分頁索引 0 代表不可關閉，資料夾頁的關閉選單無反應，移除後的第一個內容分頁也可能被誤擋。 | 改以工作階段物件辨識；最後一頁回起始畫面、可重開；資料夾頁清除監看，文字頁保留未儲存確認。`tests/test_close_sessions.py`。 |
| UI-6 | 只要任一子項不同就把雙側資料夾整列標紅，會把單側缺項、較舊與資料夾日期混為一談。 | `lib/ui/folder_presentation.py` 逐側彙整子項目紅／鋼藍狀態，名稱黑色、大小與日期灰色；狀態圖示向父層傳遞，不改內容驗證。`tests/test_folder_presentation.py`。 |
| UI-8 | Qt 反白會替圖示染藍，紅藍複合資料夾變灰；僅加深圖示配色沒有解決根因。 | `FolderSelectionDelegate` 只改選取背景，取消繪製時的選取染色並保留文字前景；清單選取狀態本身仍正常保留。 |
| UI-9 | 單檔啟動先建資料夾列表，換檔路徑又是唯讀；移除列表後若仍只依列表監看，獨立內容頁不會刷新。 | 單檔直接開內容頁，路徑換檔經主視窗驗證及捨棄確認；監看納入內容頁配對及父目錄，無列表時獨立背景刷新。`tests/test_file_paths.py`。 |
| UI-7 | 帶入兩個資料夾啟動時，掃描後仍拿清單第一項自動開內容，遇資料夾就跳錯誤提示。 | 自動開內容前確認兩端確為檔案；資料夾只留清單。`tests/test_comparison_layout.py`。 |
| HEX-1 | 同位址比較遇到中間插入資料，後面大量相同內容也被標紅。 | 內容對齊後以空白補位，保留兩側原始位址；`lib/core/binary_alignment.py`。大量重複資料可能存在其他有效配對，並非已保證最小差異。 |
| ICO-1 | 原 SVG 是平滑曲線，但直接低解析匯出、未開反鋸齒會出現鋸齒。 | `tools/export_app_icon.py` 先高解析反鋸齒算繪，再平滑縮到 16～256 像素，產生透明多尺寸 ICO。 |
| TEST-1 | 離線 Qt 平台沒有相同的 Windows 字型資料庫，不能用其截圖判斷中文字型。 | 功能測試用 offscreen；字型及實際畫面驗證用 Windows 平台。 |
| TEST-2 | 同步還在背景寫入時就讀目的檔，可能遇到存取被拒。 | 先等工作結束，再核對目的檔；現有同步 UI 測試已採條件等待。這不代表下列所有 WinError 5 都已查明。 |
| TEST-3 | 暫存檔原子替換仍曾在 `test_external_atomic_replacements_keep_watching`、`test_real_sync_preview_and_execute` 回報 WinError 5，根因尚未查明。 | 早期擴大驗證排除兩項，245 項通過；首次推送前已執行全部測試，257 項通過。未修改安全檢查或加入重試繞過；此次通過不表示已治本，排除也不是測試預設。 |
| IPC-1 | 每次啟動各建一個主視窗，無法將新的比較工作加入原視窗；Hex 背景載入與新請求同時完成時也可能重複新增分頁。 | 同帳號啟動鎖定與本機通訊傳遞請求；各資料夾工作階段獨立，加入內容分頁前統一檢查既有配對。`tests/test_single_instance.py` 驗證跨程序中文路徑、喚回、未儲存內容、監看及背景載入競態。 |
| UI-10 | 字型設定沿用緊湊介面的小字與原生微型上下箭頭，還原操作外觀不明顯。 | 共用樣式以視窗識別限定 11pt 字級、欄位與明確按鈕外觀；正式 SVG 繪製上下箭頭，再縮短欄位垂直留白。Windows 可見視窗已實際點選驗證，不設定區域 stylesheet。 |
| PKG-1 | 首次 onefile 啟動在 QtCore 回報「找不到指定的程序」；PyInstaller 沿 PATH 混入 Codex 工具環境的同名 ICU／CRT。外來 icuuc.dll 缺少 QtCore 需要的 20 個符號，Windows 系統版本則完整。 | `tools/pyi_prune.py` 依來源排除 Codex 工具 DLL，保留正式 Python／Qt 相依，不依靠人工清 PATH；`tests/test_packaging_tools.py` 補來源過濾回歸測試。 |
| SHELL-1 | 兩個右鍵命令以 Compare／SelectLeft 註冊時，平鋪選單被其他程式插開。 | manifest 改用 DualMirror01Compare／DualMirror02SelectLeft，共同前綴與連續編號；本機檔案總管已實測相鄰。 |
| SHELL-2 | 註冊資源改用新摘要目錄後，Add-AppxPackage 回報 0x80073D0B：同一套件已安裝於不同外部位置。 | 先保存並移除同名舊註冊，再加新位置；失敗移除新註冊並恢復舊位置與記錄。`tests/test_shell_registration.py` 模擬此限制及失敗回復，Windows 已實測更新。 |
| SHELL-3 | 註冊成功後檔案總管仍快取舊關聯，選單未即時出現／消失。 | 成功註冊或移除後呼叫 SHChangeNotify 更新關聯，不重啟檔案總管。 |

## 從公版移植時保留的打包注意事項

以下是來源專案已驗證的相依限制；本工具的實際建置與試跑結果記於 DEVELOPER.md。

- `lib/ui/ui_common.py` 仍 import QtUiTools；即使沒有使用 OpenGL 畫面，它的連結期相依
  `Qt6OpenGL.dll`／`Qt6OpenGLWidgets.dll` 仍須收進來。
- PATH 上 Git for Windows 的 OpenSSL 可能被混入；只剔除來源為 Git 的那份，
  保留 Python 自己的 `_ssl`、`_hashlib`、`libssl`、`libcrypto`。
- `qwindows`、`qsvg`、`qsvgicon`、`qico` 及輸入法相關資源不能因瘦身而誤刪。
- 原生 Shell 已支援 Python／EXE；onefile 每次解壓的暫存路徑不能拿來長期註冊 DLL。
  啟用時複製到 LocalAppData 的固定摘要目錄，本輪打包不變更目前帳號的真實註冊。
