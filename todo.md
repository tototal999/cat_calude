# ClaudeCat TODO

## v2 發行內容（2026-07-17）

- [x] Open WebUI 風格的深色聊天介面：側欄、模型頂欄、歡迎提示與新版輸入列。
- [x] Windows EXE 明確打包 tkinter、Tcl/Tk DLL 與資料檔，避免目標電腦缺少 tkinter。
- [x] 打包版本強制使用內建 Tcl/Tk 路徑，不受外部 `TCL_LIBRARY`／`TK_LIBRARY` 環境變數影響。

> 對應 spec：claudecat-chat-spec.md v5.6
> 順序：Part 1 → 驗收 → Part 1.5（可與 Part 2 並行）→ Part 2（閘門：LLM 設定到位）
> 更新方式：完成打 `[x]`，發現新事項加在對應區塊尾端並註記日期

---

## v6.1 — 本機文件助手（2026-07-18）

> 規格來源：[local-document-assistant-mvp.md](local-document-assistant-mvp.md)。
> 前提：此功能採離線安裝包；不要求使用者安裝 Ollama、操作命令列或下載模型／Python 套件。

### 文件助手 MVP

- [x] P6-0. 單擊桌面貓開啟貼身的快速提問泡泡；不開完整聊天視窗，Enter 後以公司內網 Qwen 回答。（2026-07-18）

- [x] P6-1. 建立「聊聊天」與「拖文件給我」兩個入口，拖檔後開啟文件工作區。（2026-07-18：pywebview 文件頁與桌寵右鍵入口）
- [o] P6-2. 已在文件索引中整合本機 MarkItDown 轉 Markdown；仍待將 Python runtime／sidecar 隨公司離線安裝包封裝，並由主程式以 `127.0.0.1` 生命週期管理。（2026-07-18）
- [x] P6-3. 支援 PDF、DOCX、PPTX、XLSX、CSV、Markdown、TXT 轉換，並保留來源 metadata。（2026-07-18：離線原生解析）
- [x] P6-4. 實作來源定位：PDF 頁碼、Word 標題／段落、PPT 投影片、Excel 工作表與儲存格範圍；不得從 Markdown 猜測 PDF 頁碼。（2026-07-18）
- [x] P6-5. 本機切塊與檢索：只將相關區塊交給公司內網 Qwen（`llm.base_url`）或未來 GGUF／llama.cpp 相容模型。（2026-07-18：文件問答已接至既有 LLM client，內網 Qwen 最小 chat-completions request 實測通過）
- [x] P6-6. 預設開啟「只回答文件內容」；無證據時回覆「此文件沒有描述此問題，無法依文件確認。」（2026-07-18：本機 evidence-first 檢索）
- [x] P6-7. 由 metadata 產生回答引用與相關內容範圍，不接受僅由 LLM 生成的引用。（2026-07-18：檔名、標題與行號）
- [x] P6-8. 實作摘要、問問題、流程／SOP、整理表格、比較文件與建議問題介面。（2026-07-18）
- [x] P6-9. 掃描型 PDF 無可擷取文字時提示需 OCR；MVP 不執行 OCR。（2026-07-18）
- [x] P6-10. 文件索引存於 `%LOCALAPPDATA%\ClaudeCat\documents\`；可移除索引且不刪原始檔，診斷 log 不記錄文件全文。（2026-07-18）
- [x] P6-10a. 移除聊天頁對 highlight.js CDN 的執行期依賴；離線時仍可閱讀程式碼區塊。（2026-07-18）

### Claude／Codex 用量

Claude／Codex limits 與聊天／文件助手完全獨立，預設 OFF。兩者首次開啟時，都必須由每位使用者在自己的電腦同意；若本機沒有 Claude 登入資料或 Codex Desktop，顯示 `No use` 並不查詢。Claude 啟用後輪詢既有 usage API；Codex 以本機 app-server 的非官方 `account/rateLimits/read` 讀取用量，不直接處理 token，Codex 更新後可能失效。（2026-07-18：實測 Plus 主窗口 12% 回傳成功）

### v6.1 驗收

- [ ] P6-A1. 離線安裝後，不需網路、Ollama 或命令列，即可使用一般聊天及文件助手。
- [x] P6-A2. PDF、DOCX、PPTX、XLSX 各以至少一份測試檔驗證：每項答案事實都有正確來源定位。（2026-07-18：單元測試）
- [x] P6-A3. 文件未提及的問題不臆測；掃描 PDF 顯示 OCR 限制。（2026-07-18：單元測試）

**2026-07-18 實測紀錄：**公司內網 Qwen endpoint 以既定模型與最小 `chat/completions` request 回應成功；文件問答 bridge 測試確認只傳遞檢索命中的來源內容與定位資訊。

**2026-07-18 瘦身與驗證：**Excel worker 改用 `openpyxl`／`xlrd`，移除 pandas/numpy；打包時排除未使用的 pyarrow、onnxruntime、grpc、oracledb 與 pypdfium2。`dist\\ClaudeCat` 為 **73.5 MiB**，已用打包 EXE 的 `--document-check` 分別驗證 PDF、DOCX、PPTX、XLSX 文件索引皆成功（exit 0）。

---

## 🔴 v2 現在卡在這（唯一 blocker）

- [x] **P1-0. 實機跑 `verify_pywebview_tk.py`**（`pip install pywebview`）✅ 2026-07-17 GO
  - [x] tkinter 窗 frame N 持續跳動（貓不被卡）— 實測 webview 開啟期間 min 9.0 fps
  - [x] webview 按鈕呼叫 Python 約 1 秒拿到回傳 — 實測 1.02s（橋接開銷 ~20ms）
  - [x] 關 webview 後 tk 窗仍存活 10 秒 — 實測存活且 +89 幀
  - 環境註記（2026-07-17）：pywebview 裝在 **Python 3.11**（pip/pyinstaller 所屬版本，
    exe 也是 3.11 打包）；PATH 上的 `python` 是 3.14，開發/驗證統一用
    `%LOCALAPPDATA%\Programs\Python\Python311\python.exe` 跑才與 exe 一致
  - 檔案名註記：spec 寫 `main.py`，實際主程式是 `cat.py`（Part 1 開發時以 cat.py 為準）

---

## Part 1 — 貓基本功能（排程＋用量開關）

- [x] P1-1. `scheduler.py`：schedule.json 載入/驗證（錯誤明說哪一筆，其餘照載）、
      tick(now) 三型判斷（daily/weekly/hourly）、lead/ontime 各自防重複、寫回
- [x] P1-2. `cat.py`（非 main.py，見下方註記）：30 秒 tick 掛入 after() 迴圈；
      彈卡（Toplevel/置頂/點關/60s 收合）；貓 alert 姿勢或加速 3 秒
- [x] P1-3. `chat.html`：Tab 骨架＋排程頁（清單＋依 type 動態欄位表單）
- [x] P1-4. `chat/window.py`：pywebview 單例＋排程 js_api（list/upsert/delete，即改即存）
- [x] P1-5. 右鍵選單「排程...」→ 開單例窗至排程分頁
- [x] P1-6. 用量監控開關：config＋選單勾選；OFF 真停輪詢；
      失敗偵測（缺檔/token/連續3次）→ 狀態轉變彈一次卡；異常標示；自動恢復
- [x] P1-7. 交談分頁：已直接實作（Part 2 程式碼同批完成，非空殼）

### Part 1 驗收（P1-8，全過才放行後續）

- [o] daily：2 分鐘後＋lead_min=1 → 提前卡與正點卡各彈一次
      *(2026-07-17 實機驗證：08:51 lead、08:52 ontime 各觸發一次，log 確認)*
- [x] lead_min=0 只彈正點；weekly 非當日不觸發；hourly 每小時該分鐘觸發
      *(test_logic.py 21/21 通過，含跨午夜 lead)*
- [x] enabled=false／刪除後不觸發 *(test_logic.py 驗證)*
- [x] schedule.json 改壞格式 → 明確指出錯誤筆，其餘正常 *(test_logic.py 驗證)*
- [o] 彈卡 60s 自動收合；點擊即關；表單即改即存、重啟生效
      *(2026-07-17 實機看過彈卡外觀正常；60s 自動收合與表單持久化尚未逐項計時驗證)*
- [ ] 排程運作期間貓不掉幀
- [ ] 用量 OFF 後 log 零 API 請求、貓恆速
- [x] 改壞 credentials → 只彈一次異常卡＋選單（異常）；修復自動恢復；ON/OFF 重啟保留
      *(test_logic.py 驗證邏輯；實機用真憑證未测)*

**2026-07-17 額外修復（實機測試中發現，spec 未列但屬合理範圍）：**
- 徽章文字寬度變化時（例如 `...` → `64% W70% | 17:00`）未重新置中，
  導致徽章長期偏移貓的中軸——已修正為文字變化時才重新置中（不影響效能修正）
- 視窗定位本身（貓＋徽章）在目前版本實測正常，兩組座標 (1100,420)/(300,250)
  皆精準命中；之前懷疑的 pywebview 主執行緒／tk 背景執行緒定位衝突未重現

---

## Part 1.5 — 基礎互動（Part 1 驗收後；與 Part 2 互不依賴）

- [x] 桌寵主視窗顯示於 Windows 工作列；可透過工作列項目的關閉按鈕結束，並保存位置。（2026-07-18）
- [x] P1.5-1. 拖曳＋位置持久化（位置存於 config.json，2026-07-17 實機驗證兩組座標精準）
- [x] P1.5-2. 點擊隨機小動作（5px 位移閾值切分點擊/拖曳，單擊觸發加速 sprint）
- [x] P1.5-3. 素材包資料夾約定 `skins/<name>/`（非 spec 原寫的 `assets/`，
      沿用既有皮膚系統）＋角色子選單＋切換持久化；缺幀自動降級
- [x] P1.5-4. 階段式睡眠：閒置計時（hover/click/用量跳動喚醒），
      達 config sleep_min 後入睡；2026-07-17 修正：交談期間持續刷新閒置計時
      （原本聊天中會被誤判閒置偷偷入睡，關窗時瞬間喚醒+當下高用量速度＝看似暴衝）
- [x] P1.5-6（新增，2026-07-17）：交談視窗貼齊跟隨——`_dock_tick()` 每 400ms
      讀 pywebview 視窗座標，貓與徽章貼齊視窗外側，拖動視窗即時跟隨；
      螢幕空間不足時自動切換左/右側停靠

### Part 1.5 驗收（P1.5-5）— 🔲 尚未逐項實機測試

- [o] 拖放任意位置，重啟在原位 *(2026-07-17 已用固定座標間接驗證定位機制正確；
      未實際做「拖曳→重啟」的手動操作)*
- [ ] 點擊即時反應；3px 內視為點擊、超過為拖曳（程式碼是 5px，見上方註記）
- [ ] 切角色即換幀、重啟保留；缺幀降級不報錯
- [ ] 想睡→熟睡兩階段可觀察；滑鼠移入驚醒；用量跳動喚醒
- [x] 交談視窗貼齊跟隨 *(2026-07-17 實機驗證：視窗從螢幕左上拖到中央，
      貓與徽章即時跟上；關窗後速度恢復正常無暴衝)*
- [ ] 排程彈卡與監控在互動期間照常（回歸 P1-8 重點項）

---

## Part 2 — LLM 交談

### 前置

- [x] P2-0. **使用者提供**：base_url=`http://example.invalid:8000/LLM/v1`，
      model=`Qwen/Qwen3.6-35B-A3B-FP8-nothink`，api_key 不需要，引擎 vLLM 0.25.0
- [x] P2-1. 端點側環境確認：chat completions 正常回應
- [x] P2-2. `/v1/models` 回 404（該端點未實作此路徑）→ 改用 config 靜態
      `fallback_models` 清單餵模型下拉選單

### 開發

- [x] P2-3. `llm.py`：chat（timeout 60s）＋ probe／list_models／export_chat／
      save_note／debug_log，錯誤明確拋出
- [x] P2-4. config llm 區塊：`llm.init(CONFIG_FILE)` 讀取
- [x] P2-5. `chat.html` 交談頁：模型下拉／對話區＋💾＋截斷灰字／
      輸入區（isComposing、送出鎖、🐱…）／匯出鈕
- [x] P2-6. `chat/window.py`：暖機探測＋聊天 js_api（send_message/list_models/
      set_model/save_note/export_chat/probe，thread 不卡 UI）
- [x] P2-7. `cat.py`：「交談...」→開窗＋貓縮 32px 停靠；關窗復原原尺寸
- [x] P2-8. 上下文：動態 system prompt（含監控狀態分支）、滑動視窗截斷、
      context 溢出降級（砍半重試一次＋灰字明說）
- [x] P2-9. 文件：匯出 chat_*.md；💾 存 note_*.md（含時間戳、模型）

### Part 2 驗收（P2-10）— 🔲 尚未執行，下一步

- [ ] 聊天期間貓不掉幀；端點離線錯誤明確顯示；開窗即知離線
- [ ] 中文選字 Enter 不誤送；生成中重按無效；視窗單例
- [ ] 模型 fallback 提示正確；切模型 history 保留
- [ ] 監控 OFF 時 prompt 注入狀態說明（貓不拿舊數字胡說）
- [ ] 匯出/存檔內容正確；關窗貓復原
- [ ] debug_log 預設關閉時 debug/ 目錄零檔案；設 true 有記錄
- [ ] 貼超長文字 → 灰字降級提示與重試；極端長度最終報錯不無限重試
- [ ] **回歸：P1-8 全數重跑通過**

---

## Part 3 — 候選池（Part 2 落地後再議，不承諾）

- [ ] 📎 檔案附加當 context（**規格已凍結於 spec 2.2 節，可直升 P2-11**）
- [ ] Mini mode（拖至邊緣縮進、懸停探頭）
- [ ] 雙擊/長按/懸停/滾輪/甩動/游標追蹤（需手勢狀態機）
- [ ] SSE 串流回覆
- [ ] 跨 session 聊天記憶
- [ ] 切角色連動聊天人設（每角色一份 system_prompt）——**待使用者確認要不要**
- [ ] Agent 委派（claude -p headless）
- [ ] 排程貪睡（snooze）

## ⛔ 已否決（不做，理由見 spec 附錄 A）

跨平台（開源時重啟）／Fork BongoCat／Fork TonyNa／clawd-on-desk 抄碼（AGPL）／
agent hooks 整合（裝現成 clawd-on-desk 即可）／window sitting／多寵／
.xlsx 解析／批次管線／排程接 LLM／錯過補償／AI 客服

---

## 📌 待使用者提供／決定

- [x] ~~verify_pywebview_tk.py 三項結果~~ → 2026-07-17 GO
- [x] ~~LLM 設定~~ → 已提供並驗證（example.invalid:8000）
- [ ] 切角色是否連動聊天人設（Part 2 驗收後定案即可）
- [ ] 📎 檔案附加要不要直升 P2-11（Part 2 驗收後定案即可）

---

## 🔵 現在卡在這（下一步）

Part 1 / Part 1.5 / Part 2 程式碼皆已完成。剩下純粹是**實機驗收**，
按順序執行 P1-8 剩餘項 → P1.5-5 → P2-10（含 P1-8 回歸），全過即結案。

---

## 🎨 ClaudeCat 介面現代化 (ChatGPT Style) 改造計畫

這是一項純 HTML/CSS/JS 介面優化計畫（參考 ChatGPT 現代深色風格），分為兩階段：

- [x] **第一階段（純換皮）**：
  - [x] 將 `chat.html` 佈局改為「雙欄式彈性佈局」（左側 Sidebar，右側 Main Chat）。
  - [x] 套用極深灰 (`#171717`, `#212121`) 現代化暗色系主題。
  - [x] 優化對話泡泡視覺，拔除邊框，最大寬度 800px 限制。
  - [x] 底部輸入區懸浮化、圓角化，並整合 📎 與 ⬆️ 按鈕圖示。
- [x] **第二階段（歷史會話與進階 UI）**：
  - [x] 實作對話持久化，在 `%LOCALAPPDATA%\ClaudeCat\sessions` 儲存/讀取對話 JSON。
  - [x] 在左側 Sidebar 顯示動態的「最近對話」清單。
  - [x] 點擊歷史紀錄可呼叫 `pywebview.api` 載入對應內容並切換。
  - [x] 導入 `highlight.js` 程式碼高亮與複製。
  - [x] 導入 `/` Slash commands 提示詞功能。

---

## 🏗️ 內部資料夾重構 (MVC-like Refactoring) 計畫

為提升專案可維護性並分離前後端邏輯，預計進行以下重構（不影響現有 UI/UX 與桌面寵物特性）：

- [x] **階段一：前端拆分**
  - [x] 建立 `frontend/` 目錄。
  - [x] 將 `chat.html` 拆分為 `index.html`、`chat.js`、`style.css`。
- [x] **階段二：後端解耦**
  - [x] 建立 `backend/` 目錄，將 `window.py` 拆解出 `routes/api.py` (負責 JsApi)。
  - [x] 建立 `backend/services/`，將 `llm.py` 移入 `llm_service.py`。
  - [x] 建立 `config/settings.py`，集中管理設定檔讀取。
- [x] **階段三：資源分離與打包修正**
  - [x] 將 System prompt 抽離為純文字 `backend/prompts/system.txt`。
  - [x] 更新 `ClaudeCat.spec`，確保 PyInstaller 能正確打包新的資料夾結構。
- [x] **重構回歸修復（2026-07-17 晚）**：`config/settings.py` 的 `load_config()`
      重構時忘了 return，`cat.py` 呼叫端拿到 None 啟動即死（「執行 exe 沒反應」）。
      已修正為回傳快照 dict，原始碼與 onedir exe 皆實測啟動存活。
      **教訓：重構後必跑一次啟動煙霧測試再打包。**
- [x] **重構殘留變數名稱修復（2026-07-17 晚）**：`cat.py` 裡面殘存的
      `_settings.load_config()` 與 `self._settings.save_config()` 沒被重構腳本替換，
      導致 NameError 啟動即死。已全數替換為 `settings.load_config()` / `self._save_config()`。
- [x] **chat.js RegExp 斷行 Syntax Error（2026-07-17 晚）**：`renderMarkdownLite()`
      中的正規表達式 literal 包含了真實 LF 換行字元，導致整個 chat.js 語法無效，
      pywebview 拒絕執行——症狀為介面載入但按鈕全無反應、模型選單空白、無法送出訊息。
      已修正為 `[\r\n]+` 跳脫寫法，並加上全域 `window.onerror` / `unhandledrejection`
      監聽器，未來 JS 錯誤直接 alert 不再靜默。
- [x] **重構遺留清理（2026-07-17 晚）**：根目錄 7 支一次性腳本與 test.pptx
      已從版控中刪除；廢棄的 `chat/` 目錄已一併清除。
- [x] **UI 微調與圖示（2026-07-17 晚）**：加入專屬藍貓圖示（`claudecat.ico`）
      並打包進 EXE；修正 `chat.js` 與 `style.css`，讓左側邊欄 ☰ 能正確收合，
      並在側邊欄與主畫面之間加上 `resize handle` 供拖曳調整寬度。
- [x] **聊天規範（2026-07-17 晚）**：將常駐原則中的聊天相關要求
      （繁體中文、簡短回覆、不確定的事不編造、長文先列大綱、有歧義主動問）

## 2026-07-17 品質與效能修復

- [x] 聊天、session 與排程文字改為安全轉義；session ID 驗證為 UUID。
- [x] 修復 PPTX 匯出未寫入檔案，以及排程編輯會遺失欄位／重啟停用項目的問題。
- [x] 附件改為在開發環境直接使用 `worker.py`，避免載入完整主程式。
- [x] 附件在解析前限制檔案大小，Worker 限制可輸出文字；附件與 PPT 工作程序均有 timeout。
- [x] `test_logic.py` 改為安全、可重複執行的 unittest，避免碰觸使用者憑證。
      加入到 `system.txt` 角色設定中。
