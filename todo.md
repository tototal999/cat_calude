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

- [x] P6-OpenPets-0. 保留 Python/Tkinter；不導入 Electron 或 OpenPets 程式碼，只採用狀態機、貼身氣泡／卡片與安全模組化概念。（2026-07-18）
- [x] P6-OpenPets-1. 素材缺口盤點已寫入 `local-document-assistant-mvp.md`；缺圖時必須安全 fallback，不得阻止既有皮膚載入。（2026-07-18）
- [x] P6-OpenPets-1a. bluecat、cowcat、ragdollcat 均已補齊 idle／sleep／error／listening／thinking／success；命名狀態圖不再混入 run cycle。（2026-07-18）
- [x] P6-OpenPets-2. `PetState` 與快速提問短答／長答貼身卡片；短答留在泡泡，超過 180 字或 4 行時展開可複製、繼續問、收合的貼身卡片。（2026-07-18）
- [x] P6-OpenPets-3. 系統匣與安全 plugin 介面：顯示／隱藏、快速提問、文件助手與結束；plugins 僅能觸發固定白名單事件，不做動態下載。（2026-07-18）

- [x] P6-0. 單擊桌面貓開啟貼身的快速提問泡泡；不開完整聊天視窗，Enter 後以執行期設定的 OpenAI-compatible LLM 回答。（2026-07-18）

- [x] P6-1. 建立「聊聊天」與「拖文件給我」兩個入口，拖檔後開啟文件工作區。（2026-07-18：pywebview 文件頁與桌寵右鍵入口）
- [o] P6-2. 已在文件索引中整合本機 MarkItDown 轉 Markdown；仍待將 Python runtime／sidecar 隨公司離線安裝包封裝，並由主程式以 `127.0.0.1` 生命週期管理。（2026-07-18）
- [x] P6-3. 支援 PDF、DOCX、PPTX、XLSX、CSV、Markdown、TXT 轉換，並保留來源 metadata。（2026-07-18：離線原生解析）
- [x] P6-4. 實作來源定位：PDF 頁碼、Word 標題／段落／表格列、PPT 投影片、Excel 工作表與儲存格範圍及欄標題；不得從 Markdown 猜測 PDF 頁碼。（2026-07-19）
- [x] P6-5. 本機切塊與檢索：採 CJK 詞組與最低相關分數，只將相關區塊交給執行期設定的 `llm.base_url` 或未來 GGUF／llama.cpp 相容模型。（2026-07-19）
- [x] P6-6. 預設開啟「只回答文件內容」；無證據時回覆「此文件沒有描述此問題，無法依文件確認。」（2026-07-18：本機 evidence-first 檢索）
- [x] P6-7. 由 metadata 產生回答引用與相關內容範圍，不接受僅由 LLM 生成的引用。（2026-07-18：檔名、標題與行號）
- [x] P6-8. 實作摘要、問問題、流程／SOP、整理表格、比較文件與建議問題介面；長文件採跨全文抽樣，UI／提示詞明示「非完整文件結論」。（2026-07-19）
- [x] P6-9. 掃描型 PDF 無可擷取文字時提示需 OCR；MVP 不執行 OCR。（2026-07-18）
- [x] P6-10. 文件索引存於 `%LOCALAPPDATA%\ClaudeCat\documents\`；可移除索引且不刪原始檔，診斷 log 不記錄文件全文。（2026-07-18）
- [x] P6-10a. 移除聊天頁對 highlight.js CDN 的執行期依賴；離線時仍可閱讀程式碼區塊。（2026-07-18）

### Claude／Codex 用量

Claude／Codex limits 與聊天／文件助手完全獨立，預設 OFF。兩者首次開啟時，都必須由每位使用者在自己的電腦同意；若本機沒有 Claude 登入資料或 Codex Desktop，顯示 `No use` 並不查詢。Claude 啟用後輪詢既有 usage API；Codex 以本機 app-server 的非官方 `account/rateLimits/read` 讀取用量，不直接處理 token，Codex 更新後可能失效。（2026-07-18：實測 Plus 主窗口 12% 回傳成功）

### v6.1 驗收

- [x] P6-A1. 使用者已接受文件助手使用公司內網 LLM；文件與索引留本機，不需 Ollama 或命令列。（2026-07-19）
- [o] P6-A2. PDF、DOCX、PPTX、XLSX 各以至少一份測試檔驗證索引與原生來源定位；「長文件完整摘要／每項答案事實」尚未完成端對端語意驗證，不宣稱完成。（2026-07-19）
- [x] P6-A3. 文件未提及的問題不臆測；掃描 PDF 顯示 OCR 限制。（2026-07-18：單元測試）

**2026-07-18 實測紀錄：**LLM endpoint 可由使用者執行期設定；公開 repo 不記錄內網 URL、模型或憑證。文件問答 bridge 測試確認只傳遞檢索命中的來源內容與定位資訊。

**2026-07-18 瘦身與驗證：**Excel worker 改用 `openpyxl`／`xlrd`，移除 pandas/numpy；打包時排除未使用的 pyarrow、onnxruntime、grpc、oracledb 與 pypdfium2。新版 `dist\\ClaudeCat` 為 **77.0 MiB**；`verify_packaged_documents.py` 已以打包 EXE 驗證 PDF、DOCX、PPTX、XLSX 的索引與來源定位。

---

## v6.2 — 桌面 AI 工具箱（2026-07-19）

> 規格來源：[desktop-ai-toolbox-mvp.md](desktop-ai-toolbox-mvp.md)。公司 LLM 只能使用使用者執行期設定的內網端點；不把端點、模型或 API Key 寫入 repo。

- [x] P7-1. JSON 工具：Format、Minify、Validate（行／欄錯誤）、Copy、搜尋、Tree View／JSONPath；格式化與驗證不使用 LLM。（2026-07-19）
- [x] P7-2. 翻譯工具：英／繁中、一般／技術／商務／中英對照；保留程式碼與表格；本機術語表。（2026-07-19）
- [x] P7-3. 模型模式：一般 UI 顯示自動／快速／高品質／程式分析／翻譯，不直接曝露模型 ID。（2026-07-19）
- [x] P7-4. 任務模型路由：聊天、翻譯、文件、程式分析、錯誤分析可各自指定模型，未設定時安全退回預設模型。（2026-07-19）
- [x] P7-5. 進階模型設定與健康檢查：Provider、端點、預設模型、逾時、模式／任務對應；API Key 維持由安裝／執行期設定提供，不在 UI 編輯。（2026-07-19）
- [x] P7-6. 統一桌寵右鍵入口：快速提問、LLM 介面、文件助手、JSON 工具、翻譯、模型設定與排程皆可直接開啟；Skin 與桌寵設定保留子選單，移除重複的 Plugins 選單。（2026-07-19）
- [x] P7-A1. JSON 工具在 LLM 離線時完全可用；非法 JSON 顯示正確行、欄，並限制輸入大小／深度／節點數。（2026-07-19：確定性單元測試）
- [o] P7-A2. 翻譯與健康檢查錯誤直接顯示；程式碼／SQL／JSON Key／API path／檔名／錯誤碼以佔位符實際鎖定並驗證還原；待使用者內網端點實機確認。（2026-07-19）
- [x] P7-A3. 路由、設定 merge、sidecar 模型覆寫、本機 OpenAI-compatible 假端點與 worker／排程反例均有回歸測試。（2026-07-19：Python 3.11 `test_logic.py` 全數通過、`node --check frontend/chat.js`、`git diff --check`；測試數量見 [in_progress.md](in_progress.md)）
- [x] P7-A4. 已於第三輪修正後重新打包 `ClaudeCat.exe` 並執行啟動煙霧測試；啟動 5 秒仍存活，且 `verify_packaged_documents.py` 驗證 PDF／DOCX／PPTX／XLSX 索引與來源定位通過。（2026-07-19）

### 已知後續風險（不得宣稱已完成）

- [ ] P6-R1. 含少量浮水印文字的掃描 PDF 仍可能被視為可讀；需做逐頁低文字量警示，不能只判斷「完全無文字」。
- [ ] P6-R2. Word 的頁首頁尾／文字方塊與文件更新後的索引失效偵測（檔案 hash／mtime）尚未實作。
- [x] P7-R1. 一般聊天的 XLSX worker 已讀取全部工作表，並在任一工作表超過 10,000 列時明確輸出截斷警告。（2026-07-19：回歸測試）
- [x] P7-R3. PPTX worker 同時支援 `# 標題` 與 `## Slide 標題` 分頁；沒有合法分頁時明確失敗，不再靜默產生單頁。（2026-07-19：回歸測試）
- [ ] P7-R2. Health Check 目前只驗證聊天模型；仍待逐一驗證已設定的翻譯／文件等任務路由。

---

## v7 — 企業 AI 工作台（開發中）

> 第一性原理分析與完整邊界見 [enterprise-ai-workbench-first-principles.md](enterprise-ai-workbench-first-principles.md)。
> 不以 Dashboard 或模型數量作為完成標準；先證明一條 Workflow 能安全產生可交付成果。

### M0：產品邊界

- [x] P8-0. 凍結「企業 AI 工作台」定位；AI OS 僅作長期願景。
- [x] P8-1. 維持公司 LLM／本機 llama.cpp 路由；Claude／Codex 不參與 Workflow，除非未來另行核准資料政策。
- [x] P8-2. 首條垂直 Workflow 確認為「文件會議包」。

### M1：Workflow 核心

- [x] P8-3. 定義 Workflow Definition、Run、StepResult 與 Artifact。
- [x] P8-4. 實作白名單 Step Handler；第一版禁止任意 plugin 執行碼。
- [x] P8-5. 以 atomic JSON 保存執行狀態；支援完成、失敗、取消與有限重試。
- [x] P8-A1. 每一步可追蹤輸入摘要、輸出、時間與安全錯誤；失敗不得標示完成。

### M2：文件會議包

- [x] P8-6. 串接文件解析／檢索 → 摘要 → 會議重點 → 可選翻譯 → Markdown Artifact。
- [x] P8-7. Workspace 顯示目前步驟、來源、coverage 與已完成 Artifact。
- [ ] P8-A2. 使用者拖入 PDF／DOCX 後三次操作內取得 Markdown；中途失敗仍保留已完成成果。
- [x] P8-A3. 以打包 EXE 完成端對端文件會議包驗收。

> 2026-07-19：失敗／取消 Run 可建立新 Run 重新執行，保留 `retry_of` 且最多 3 次；
> Workspace 直接顯示 coverage、來源定位與部分／完整 Artifact，不保存來源全文。
> 新版 77.1 MiB EXE 已通過四格式文件定位、DOCX → 證據 → loopback 假 LLM → Markdown Artifact，
> 並啟動 8 秒存活。P8-A2 仍等待使用者依 `USER_TEST.md` 實際點選確認，因此不先勾選。

### v7 已知問題修正（2026-07-19）

- [x] P8-R1. **重試唯一性與防重入**：來源 Run 以 `retry_to` 原子宣告唯一後繼；
      同一失敗 Run 第二次重試會明確拒絕，沿鏈仍最多 3 次。前端建立／重試期間會停用按鈕，
      防止快速雙擊產生並行 Run。
- [x] P8-R2. **損毀 Run 回退**：`latest_run()` 依 mtime 逐筆尋找最近有效 JSON，
      最新一筆損毀時會回退到次新的有效 Run，不再讓 Workspace 永久失效。
- [x] P8-R3. **Run／Artifact 保留與清理**：自動保留最近 50 筆已結束 Run、所有執行中 Run
      與最多 5 筆損毀 JSON；同步刪除淘汰／孤立 Artifact。文件頁新增「清理 Workflow 歷史」，
      可刪除已結束 Run 與 Markdown 成果，執行中工作保留。

> 2026-07-19 獨立測試同時確認正常的項目：不支援副檔名回傳明確中文錯誤、執行中取消會標記
> `cancelled` 並保留 partial Artifact、translate 步驟產出含翻譯的 Artifact、沿重試鏈的
> 上限正確生效、`verify_packaged_workflow.py` 打包 E2E 獨立重跑為
> `QA_RESULT|STATUS:PASS`、`dist\ClaudeCat` 實測 77.1 MiB 與記載相符。
>
> 修正後新增回歸：同一來源 Run 第二次重試被拒、最新壞 JSON 回退、50 筆保留上限與手動清理
> 均通過；全專案測試及修正版 EXE 文件／Workflow／啟動驗證通過。
>
> 2026-07-19 獨立複驗（以原先抓到 P8-R1～R3 的同一組探測腳本重跑）：
> R1 對同一失敗 Run 第二次重試已被拒（先前連續 6 次全部成功）；
> R2 以「兩筆 Run、弄壞最新那筆」的真實情境確認會回退到次新的有效 Run；
> R3 建立 60 筆後實際裁切為 50 筆 Run 與 50 個 Artifact，pending Run 未被裁切，
> `clear_history()` 正確保留執行中工作。三項修正均通過。

### v7 新發現問題修正（2026-07-19）

- [x] P8-R4. **崩潰 Run 復原**：每次啟動產生 process session id；讀取、建立、清理或重試前，
      會把前一個 session 留下的 pending／running Run 標記為 failed，寫入明確中斷原因，
      保留 partial Artifact 並允許重新執行。手動清理不再把殭屍誤認為執行中工作。
- [x] P8-R5. **損毀 Run Artifact 保護**：以 Run JSON 檔名中的 UUID 將最近 5 筆損毀 Run
      加入保留集合；自動 prune 不再刪除其 Markdown 成果。超出診斷保留上限或使用者明確
      執行清理時，才會連同損毀 Run 一起移除。
- [x] P8-R6. **重試最新紀錄順序**：先寫入舊 Run 的 `retry_to`，最後才寫新 Run，
      retry 返回後 `latest_run()` 立即指向新 pending Run。若中斷造成 `retry_to` 指向不存在
      的 Run，下次重試會清除失效指標並重新建立，不形成死路。

> P8-R4～R6 回歸已覆蓋：stale running 復原為可重試 failed 且可清理、保留中壞 JSON 的
> Markdown Artifact 不被 prune、retry 後 latest 立即指向新 Run。全專案測試與修正版
> EXE 四格式／Workflow／啟動驗證均通過。

### 後續里程碑

- [ ] P8-8. 統一 Workspace：拖放／貼上、確定性格式辨識、Workflow 建議與最近 Run。
- [ ] P8-9. 第二批 Workflow：Log Triage 與只讀 SQL Review。
- [ ] P8-10. Plugin Catalog：內建 Manifest、版本、輸入類型與權限。
- [ ] P8-11. 工作導向 Dashboard：Provider、目前步驟、最近成功／失敗與 Artifact。

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
      *(`test_logic.py` 的 `SchedulerTests` 已覆蓋 daily、weekly（含非當日）、hourly、跨午夜 lead 與壞 JSON；全套測試通過，2026-07-19)*
- [x] enabled=false／刪除後不觸發 *(test_logic.py 實際建立 disabled 項目並呼叫 `delete()` 驗證)*
- [x] schedule.json 改壞格式 → 明確指出錯誤筆，其餘正常 *(test_logic.py 驗證)*
- [x] 彈卡 60s 自動收合；點擊即關；表單即改即存、重啟生效
      *(2026-07-19 人工驗收：彈卡 10:55:06.066 出現、10:56:06.129 消失，共 60.063 秒；
      排程寫入後既有規則欄位保留)*
- [ ] 排程運作期間貓不掉幀
- [x] 用量 OFF 後 log 零 API 請求、貓恆速
      *(2026-07-19 人工驗收：OFF 連續 4.3 分鐘，超過 poll_interval=180 秒，無 poll／usage／codex 記錄)*
- [o] 改壞 credentials → 只彈一次異常卡＋選單（異常）；修復自動恢復；ON/OFF 重啟保留
      *(`api.py` 僅驗證 credentials 讀取；桌寵監控、彈卡與重啟持久化尚未端對端驗證，2026-07-19)*

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
      達 config sleep_min 後入睡；2026-07-19 修正：閒置睡眠不再依賴可選的用量監控，
      人工複驗監控 OFF 閒置 95 秒入睡、滑鼠移入立即驚醒。
      （原本聊天中會被誤判閒置偷偷入睡，關窗時瞬間喚醒+當下高用量速度＝看似暴衝）
- [x] P1.5-6（新增，2026-07-17）：助手視窗貼齊跟隨——`_dock_tick()` 每 400ms
      讀 pywebview 視窗座標，貓與徽章貼齊視窗外側，拖動視窗即時跟隨；
      螢幕空間不足時自動切換左/右側停靠；2026-07-19 修正所有工具分頁皆要求停靠，
      人工複驗非 Chat 分頁不再遮擋內容；同日發現關閉最大化視窗會讓還原尺寸的貓出界，
      已補啟動／拖曳／尺寸還原的完整夾邊（`_clamp_pet_position()`）。
      2026-07-19 人工複驗：開排程→最大化→關閉後，貓落在 (1238,640)-(1366,768)
      完整在 1366x768 畫面內，徽章亦被夾住，不再出界。

### Part 1.5 驗收（P1.5-5）— 🟡 已部分人工測試

- [x] 拖放任意位置，重啟在原位 *(2026-07-19 人工驗收：拖曳後 (636,227)，
      重啟 log 顯示 requested／actual 均為 (636,227))*
- [x] 點擊即時反應；5px 內視為點擊、超過為拖曳
      *(2026-07-19 人工驗收：點擊立即進入 listening，泡泡在貓右側 8px 開啟)*
- [x] 切角色即換幀、重啟保留；缺幀降級不報錯
      *(2026-07-19 人工驗收：ragdollcat 切 bluecat 立即生效，重啟仍為 bluecat)*
- [x] 想睡→熟睡兩階段可觀察；滑鼠移入驚醒；用量跳動喚醒
      *(2026-07-19 人工複驗：監控 OFF 閒置 95 秒入睡，滑鼠移入立即驚醒)*
- [x] 助手視窗貼齊跟隨 *(2026-07-17 已驗證 Chat；2026-07-19 已驗證排程／JSON／翻譯／文件／設定頁停靠且不遮擋內容；同日複驗最大化後關閉的夾邊，貓與徽章均完整留在畫面內)*
- [x] P1.5-7（新增，2026-07-19）：快速提問泡泡可由真正的 Windows Esc 鍵關閉；首次工具測試的失敗是 VK_PACKET 注入限制造成的假陽性，保留輸入框 Esc 綁定作防禦性處理。
- [ ] 排程彈卡與監控在互動期間照常（回歸 P1-8 重點項）

---

## Part 2 — LLM 交談

### 前置

- [x] P2-0. LLM endpoint、模型與憑證由每台電腦的執行期 `config.json` 提供；公開 repo 僅保留泛用設定範例。
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
- [x] P2-8. 上下文：基礎 system prompt、滑動視窗截斷、
      context 溢出降級（砍半重試一次＋灰字明說）
- [x] P2-9. 文件：匯出 chat_*.md；💾 存 note_*.md（含時間戳、模型）

### Part 2 驗收（P2-10）— 🔲 尚未執行，下一步

- [ ] 聊天期間貓不掉幀；端點離線錯誤明確顯示；開窗即知離線
- [ ] 中文選字 Enter 不誤送；生成中重按無效；視窗單例
- [ ] 模型 fallback 提示正確；切模型 history 保留
- [x] Claude／Codex limits 不注入聊天 prompt；聊天與文件助手與 limits 開關完全獨立。
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
- [x] ~~LLM 設定~~ → 由使用者在執行期 `config.json` 提供；不記錄於公開 repo。
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
  - [x] 程式碼區塊提供複製按鈕；離線版不載入語法高亮套件。
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
