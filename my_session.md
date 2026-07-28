# Session 摘要
**儲存時間**：2026-07-28 10:55
**工作目錄**：C:\Users\TF000054\claude\claude-cat

## 工作目標
承接 7.0.6 的實機回報。起點是「長回答面板沒有關閉方式」，兩次修正都被回報「實測沒改變」，
因而做了一次全專案盲點盤查，並依盤查結果補強版本可見性與發布驗證。後續由使用者實機回報
持續衍生：文件分析結果落地、關閉拖放、移除 MarkItDown、文件去重與時間戳 ID、PDF 完整分析、
移除流程 SOP，最後同步簡報與大綱。版本從 7.0.6 一路發到 7.3.1。

## 已完成事項

**UI 修正（起點）**
- 長回答面板（`_show_answer_panel`）補上標題列 × 關閉鈕，`focus_set()` 改 `focus_force()`。
  無邊框（overrideredirect）視窗的 `focus_set()` 只設 Tk 內部焦點，搶不到 Windows 鍵盤焦點，
  所以原本 Escape 沒反應。

**盲點盤查**（完整報告在 `~/.claude/plans/compressed-greeting-sunrise.md`）
- 測試覆蓋：`cat.py` 1452 行只被 4 個測試碰到，且全用 `object.__new__` 繞過 `__init__`，
  `ClaudeCat.__init__` 從未被執行過。`tray_service.py`、`winalpha.py` 整個模組零測試。
  `api.py:128` `_merge_scoped_limits`（68 行純資料轉換）零測試。`chat.js` 55 個函式只測到 5 個。
- 假測試：`test_logic.py:410` 是恆真式（兩邊呼叫同一函式）；`:1279` 的 hasattr 檢查永不失敗；
  `test_frontend_policy.js` 的假 thenable 讓 callback 永不執行。
- 安全性查過沒問題（api_key 不進 repo、`public_settings()` 過濾、endpoint 禁帶 key、
  sidecar 強制 127.0.0.1、dist 有洩漏黑名單）；`chat.js:464` 未 escape 的 innerHTML 只吃硬編
  PROMPTS，不是漏洞。

**7.1.0 — 版本單一來源與真正的 smoke test**
- `cat.py` 新增 `__version__`，啟動 log 與右鍵選單第一列顯示；`build-release.ps1` 改為讀取它，
  `-Version` 降為選用斷言參數，不一致直接中止。
- step 8 從「process 8 秒後還活著」改為輪詢打包版 log 等 `started: version=<版本>`，
  出現 `crashed` 即失敗。**實測驗證**：注入 `time.sleep(120)` 後 process 全程存活，舊檢查會
  PASS，新檢查正確失敗。
- 刪除 `config/settings.py` 的 `save_config()`：零呼叫，且寫的是模組層 config 全域整份快照，
  會覆蓋其他 owner 的鍵——正是 `merge_config` docstring 要避免的。改成原子寫入是錯的方向。

**7.1.1 — 排程政策 bug**
- `feature-policy.json` 的 `"schedule": false` 只關掉介面（選單隱藏、bridge 三個方法被擋），
  但 `_schedule_tick` 每 30 秒照跑，`scheduler.py` 全檔沒有 policy 參照。結果使用者殘留的
  `schedule.json`（7/17 建的「彈卡外觀測試」daily 08:55）持續彈卡，且已無任何介面可刪除。
- 修法：`_schedule_tick` 開頭檢查 `policy.is_enabled('schedule')`，關閉時直接 return 且不重排
  （政策是編譯期烘進去的，執行中不會變）。不觸碰使用者的 schedule.json。

**7.2.0 — 文件分析結果落地**
- 六種操作（快速摘要、完整分析、流程 SOP、整理表格、文件問答、比較文件）全部經過
  （SOP 已於 7.3.1 移除，現為五種）
  `backend/routes/api.py` 的 `_remember()` 單一出口存檔。
- 存 `%LOCALAPPDATA%\ClaudeCat\documents\analyses\<uuid>.json`，每份文件上限 20 筆，
  tmp + `replace()` 原子寫入；按 × 刪除文件時一併刪 analyses 檔。
- 前端 `restoreLatestAnalysis()`：點選文件自動帶回最後一次結果（含來源卡片與 coverage），
  上方灰字標示是哪一種分析、何時跑的。
- 踩到並修掉的雷：原本 `ANALYSES_DIR` 寫成模組載入時計算的常數，但測試用
  `patch.object(documents, 'DOCUMENTS_DIR', ...)` 改路徑，常數 patch 不到 → 測試會寫進真實
  `%LOCALAPPDATA%`。改成 `_analyses_path()` 每次呼叫才從 `DOCUMENTS_DIR` 推導。

**7.2.1 — 關閉拖放**
- 全專案原本沒有任何 drag/drop 實作，但按鈕寫著「拖文件給我」。拖檔進去會落入 WebView2 預設
  行為導航到 `file:///`，而 `request_open()` 只做 `show()` 不重載頁面，UI 會壞到重啟為止。
- 前端 module scope 攔截 `dragover` 與 `drop` 並 `preventDefault()`（只攔 drop 沒用，
  瀏覽器在 dragover 階段就接手了）。按鈕改成「選擇文件」。

**7.2.2 — 移除 MarkItDown**
- `_to_markdown()` 只把結果寫進索引的 `markdown` 欄位，全專案無消費端；打包版也沒帶這個套件，
  等於每次 ingest 空轉（開發模式跑真實轉檔，打包版 import 失敗被吞）。
- 不採用的量化依據：`magika` 是硬相依，帶進 `onnxruntime`(31.7MB) + `numpy`(55.6MB)，
  約 113 MB，與「不帶入 pandas／numpy」的既有決定衝突；且輸出是無頁碼／投影片編號的扁平
  Markdown，撐不起 P6-4 的來源定位。
- 既有索引檔留著 `markdown` key 不影響讀取，現有文件不用重新解析。

**7.2.3 — 文件去重與時間戳 ID**
- 使用者回報「關閉後看不到分析結果」。實際上功能正常，但有**兩份同名索引**（09:17 與 10:12 各建一次
  同一個 PPTX），清單標籤一模一樣，點到沒有分析的那份。
- 根因：`ingest()` 無條件 `uuid.uuid4()`，完全沒有去重。改為先算 SHA-256，內容相同就沿用既有索引
  （檔名變了就更新顯示名稱），內容改了才建新索引——這同時就是「強制重建」的自然路徑。
- 文件 ID 從 uuid4 改為 `YYYYMMDDHHMMSS`（同秒衝突加 `_N`）。使用者原本說 `YYYYMMDDMISS`，
  少了小時會讓 09:17:30 與 10:17:30 撞號，已補上 HH。`safe_document_id()` 同時接受舊 uuid4，
  既有索引不用重建。
- 清單顯示建立時間；7.2.3 前的索引沒有 `indexed_at`，改用索引檔 mtime 補上。
- **修掉我自己的 regression**：`test_logic.py` 加 `setUpModule()`。那些 api 層測試只 mock LLM
  沒 mock 儲存路徑，7.2.0 的 `_remember()` 讓它們開始寫進真實 `%LOCALAPPDATA%`（目錄裡的
  `550e8400-…json` 就是測試垃圾，已刪）。
- **建置 step 6 抓到的**：`workflow_service.py:213` 也用 `uuid.UUID()` 驗證 document_id，
  時間戳 ID 會被擋。改呼叫 `documents.safe_document_id()`，該函式因跨模組使用而改為公開命名。

**7.3.0 — PDF 完整分析**
- `_full_presentation_summary` 原本硬性要求所有 chunk 是 `powerpoint_slide`，PDF 的 `pdf_page`
  直接被拒。改用 kind → 單位對照表（投影片／頁），提示詞跟著說「逐張」或「逐頁」。
- DOCX／XLSX 仍擋著：段落與列的 chunk 太細，一份文件會炸成上百次 LLM 呼叫。
- 新增 `FULL_ANALYSIS_MAX_BATCHES = 40`（240 頁）。超過不分析，透過既有 coverage 機制誠實
  回報部分涵蓋，而不是無聲跑十幾分鐘。順帶修掉成功路徑直接回傳 `evidence['coverage']`、
  沒反映實際處理量的問題。
- 按鈕改名「完整分析（不抽樣）」，與旁邊的「快速摘要（抽樣）」形成對照。

**7.3.1 — 移除流程 / SOP**
- 使用者決定移除。`sop` action、標籤與按鈕全部拿掉，全 codebase 零殘留。
- 既有已存的 `kind='sop'` 分析結果仍可正常還原（label 是存下來的），不需要資料遷移。
- 同時把「若來源不足請明確說明」這類防呆補進 `summary` 的指令——移除 SOP 後它是唯一還缺的。

**簡報與大綱同步**
- `tools/sop-deck-gen.js`：移除「流程 SOP」字樣，補上完整分析（不抽樣）、12 個區塊抽樣說明、
  分析結果自動保存、重複選檔沿用既有索引。已重新產生 `桌寵與LLM.pptx`（15 張），
  並用 python-pptx 逐項驗證 7 個檢查點全過。
- `桌寵與LLM大綱.md` 第 8 節與功能表同步。

## 重要決定
- **版本號單一來源是 `cat.py` 的 `__version__`**，`-Version` 只是斷言。發布只改那一處。
- **政策關閉某功能時，行為層也要一起關**，不能只隱藏介面——否則會出現「使用者看得到影響、
  卻沒有任何介面可以處理」的陷阱。排程是第一個案例，日後加政策開關要一併檢查行為層。
- **失敗的分析結果不落地**：存了下次開啟會變成看起來像正常答案的舊錯誤訊息。
- **MarkItDown 若日後重啟，走 sidecar 而非打包**（使用者自己的 MVP 規格早就這樣設計），
  且只用於現有原生擷取器不支援的格式（.msg／.html／.epub／圖片）與掃描型 PDF。
- **每個新測試都驗證過會失敗**：排程守衛改 `if False and ...`、拖放拿掉 `preventDefault()`，
  確認測試確實會紅，不是恆真的假測試。這是這次盤查抓到假測試後養成的習慣。

## 待辦事項
- [ ] 盤查報告第 3–6 項未做：補純函式測試（`_frame_interval`／`SPEED_TABLE`、
      `_drain_tray_actions`、`_merge_scoped_limits`）、一個真正執行 `ClaudeCat.__init__` 的測試、
      修 `test_logic.py:410`／`:1279` 假測試與 JS 假 thenable、debug log 保留上限
- [ ] `request_open()`（`backend/window_main.py:141`）重新顯示時不確認 URL；拖放已堵住，但若
      日後有其他方式讓 webview 導航走（例如回答內容裡的連結），一樣會卡住直到重啟
- [ ] `local-document-assistant-mvp.md`、`enterprise-ai-workbench-first-principles.md` 仍有
      MarkItDown 敘述，刻意保留為歷史設計，未來若確定不走 sidecar 可清掉
- [ ] `桌寵與LLM.pdf` 待手動用 PowerPoint 從新版 pptx 匯出（本機沒裝 LibreOffice）
- [ ] gemma 格式測試（是否需 `# 標題` 格式才能產簡報）——延續自更早的 session，一直未處理

## 關鍵程式碼

```python
# backend/routes/api.py：六種文件操作的單一落地出口
def _remember(document_id, kind, label, result):
    """Persist a finished analysis, then hand it back unchanged."""
    if not result.get('error'):   # 失敗不存，否則下次開啟會顯示舊錯誤
        documents.save_analysis(document_id, kind, label, result)
    return result
```

```python
# cat.py：政策關閉排程時連行為層一起停，且不重排（政策編譯期固定）
def _schedule_tick(self) -> None:
    if not policy.is_enabled('schedule'):
        return
```

```powershell
# tools/build-release.ps1 step 8：等 Tk 真的寫出啟動行，不再只看 process 活著
$expectedStart = "started: version=$Version"
if ($logText -match 'crashed') { throw "Packaged GUI logged a crash. See $guiLog" }
if ($logText.Contains($expectedStart)) { $startedLogged = $true; break }
```

## 重要檔案
- `cat.py` — `__version__`、`_schedule_tick` 政策守衛、`_show_answer_panel` 關閉鈕
- `tools/build-release.ps1` — 版本校驗、step 8 log 驗證
- `backend/services/document_service.py` — 分析落地（`save_analysis`／`load_analyses`／
  `latest_analysis`），已移除 `_to_markdown()`
- `backend/routes/api.py` — `_remember()`、`latest_document_analysis` bridge 方法
- `frontend/chat.js` — 拖放攔截（module scope）、`restoreLatestAnalysis()`
- `tools/test_frontend_policy.js` — 新增會真正觸發 handler 的拖放斷言
- `~/.claude/plans/compressed-greeting-sunrise.md` — 完整盲點盤查報告

## 其他備註
- 建置指令現在不必帶版本：`powershell -NoProfile -ExecutionPolicy Bypass -File tools\build-release.ps1`
- 測試：`%LOCALAPPDATA%\Programs\Python\Python311\python.exe -m unittest test_logic`（110 條）
- 實機測試前務必先關掉舊的 ClaudeCat process，否則單一實例 mutex 只會喚醒舊視窗；
  確認版本看右鍵選單第一列或 log 的 `started: version=`
- 本機沒裝 GitHub CLI (`gh`)、LibreOffice/soffice
