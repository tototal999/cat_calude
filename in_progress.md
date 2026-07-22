# ClaudeCat 進度報告

> 最後更新：2026-07-22；目前交付版本以本節與 release manifest 為準，後文較小體積數字為歷史紀錄。
> 對應 spec：claudecat-chat-spec.md v5.6
> 對應 TODO：todo.md

---

## 已完成功能總覽

### 目前發布快照

- v7.0.0 onedir：81.4 MiB、2,667 個檔案；EXE SHA-256 已與 manifest 核對。
- 92/92 業務測試與 8/8 發布驗證通過，包含 GUI、公司部署、四格式文件及文件 Workflow。
- 目前政策停用 JSON、進階模型設定、排程、文件會議包、比較文件與聊天附件；其餘功能維持開放。
- 發布 log 與 manifest 已產生；正式公司發布仍待程式碼簽章，且本輪 manifest 為 `git_dirty`。

## v7 企業 AI 工作台（2026-07-19，開發中）

- 新增 `workflow_service.py`：內建白名單 Workflow、atomic JSON Run、StepResult、取消、部分／完整 Markdown Artifact。
- 首條「文件會議包」已串接 PDF／DOCX 證據檢索、摘要、會議重點、可選英文翻譯與 Markdown 匯出。
- 文件頁可背景啟動 Workflow、輪詢每一步狀態、取消執行，並在關閉重開後讀取最後一次 Run。
- 摘要完成即保存部分 Artifact；後段 LLM 或匯出失敗時不刪除既有成果，且 Run 不會誤標完成。
- 失敗／取消 Run 可重新執行，建立新的可稽核 Run 並保留來源 Run，單一重試鏈最多 3 次。
- Workspace 直接顯示抽樣 coverage、來源定位與 Artifact；Run 不保存文件來源全文。
- Router 沿用文件任務模型；公司 LLM／本機 llama.cpp 邊界不變，Claude／Codex 不參與 Workflow。
- 公司內部建置使用受 Git 忽略的 `company-defaults.json`，將公司端點與模型白名單編譯進 EXE；乾淨使用者不需旁掛設定檔，既有外部 URL／非核准模型會被強制改回公司設定。
- 新版 `dist\ClaudeCat` 為 78.1 MiB（2026-07-20 建置）；四格式文件定位與打包文件會議包 E2E 均通過，啟動 8 秒存活。
- 尚待使用者依 `USER_TEST.md` 人工確認三次操作內取得 Markdown、來源／coverage 顯示與重試按鈕。
- 2026-07-19 獨立測試發現的 P8-R1～R3 已修正：同一來源 Run 只允許一個 `retry_to`，
  建立／重試按鈕防雙擊；`latest_run()` 會略過壞 JSON 回退到最近有效 Run；歷史自動保留
  最近 50 筆已結束 Run、執行中 Run 與最多 5 筆損毀 JSON，並同步清除多餘 Artifact。
  文件頁另提供手動清理入口，且不刪除執行中工作。
- 2026-07-19 獨立測試確認正常：不支援副檔名回傳明確中文錯誤、執行中取消標記 `cancelled`
  並保留 partial Artifact、translate 步驟產出含翻譯的 Artifact、沿鏈重試上限生效、
  `verify_packaged_workflow.py` 重跑為 `QA_RESULT|STATUS:PASS`、`dist\ClaudeCat` 實測 77.1 MiB。
- 2026-07-19 修正後獨立複驗：以原先抓到問題的同一組探測腳本重跑，P8-R1～R3 三項修正
  **全部通過**（第二次重試被拒、兩筆 Run 弄壞最新那筆會回退到次新有效 Run、建立 60 筆
  實際裁切為 50 筆且 pending 未被裁切）。
- 同輪發現的 P8-R4～R6 已修正：以 process session 辨識並復原前次崩潰留下的
  pending／running Run；損毀 Run 依檔名 UUID 保留其 Markdown Artifact；retry 改為最後寫
  新 Run，`latest_run()` 立即指向新 pending Run，失效 `retry_to` 也可自動修復。
- P8-R4～R6 回歸與修正版 EXE 複驗通過：stale Run 可重試／清理、損毀 JSON 不誤刪成果、
  retry 最新順序正確；四格式文件、完整 Workflow 與 8 秒啟動均 PASS，大小維持 77.1 MiB。
- 2026-07-21 獨立複驗 P8-R4～R6：以原先抓到問題的同一組探測腳本重跑，六項全通過——
  前一 session 的 `running` Run 自動標記 failed（含中斷步驟）並可重試／可清除，
  本行程的 `pending` Run 未被誤殺；損毀 Run JSON 的 Markdown Artifact 確實保留，
  超過 `MAX_CORRUPT_RUNS=5` 才淘汰；retry 後 `latest_run()` 立即指向新 Run。
  `verify_packaged_workflow.py` 為 `QA_RESULT|STATUS:PASS`，`dist\ClaudeCat` 實測 78.1 MiB。
- 2026-07-21 查證：config 的 `llm.model` 與 log 中 `model=` 不一致並非缺陷。
  `llm_service.py` 送出的 payload 用 config 值，log 記錄的是伺服器回應的
  `data.get('model', model)`，即端點實際解析後使用的模型；兩者本就可能不同。
  已將執行期 `config.json` 的 `llm.model` 對齊為端點實際服務的完整名稱，並實際發送
  測試請求確認端點接受完整名稱（送出與回報一致）。此後不再依賴端點的別名解析，
  避免未來端點取消別名時出現不易聯想到設定檔的「模型不存在」錯誤。
  註：`config.json` 屬每台電腦的執行期設定，不進版控。

## 公司功能政策（2026-07-21）

- 新增 `config/policy.py`：由專案根目錄的 `feature-policy.json` 決定哪些功能開放，建置時嚴格驗證並
  編譯進 EXE。政策不寫回 `config.json`，使用者無法在 App 內改回；缺失或損壞時停止建置／啟動。
- 關閉的功能在右鍵選單、側欄分頁與系統匣三處**完全隱藏**（非灰色不可點）。
- 真正的閘門在 JsApi：`backend/routes/api.py` 以單一 `_GATED_METHODS` 對照表包裝 32 個方法，
  被關閉者一律回「此功能已由公司政策停用。」。實測直接呼叫 bridge 確認擋得住，不是只藏選單。
- 子功能可獨立關閉：文件會議包、比較文件、附件分析、簡報匯出 PPTX、Claude／Codex 用量。
- **`chat` 與 `quick_question` 為必要功能，不可關閉**：兩者都是向公司 LLM 提問的入口。
  以 `MANDATORY_FEATURES` 在程式端強制開啟，手改 JSON 設 `false` 無效（記錄警告）；
  網頁顯示鎖定且輸出恆為 true，實測用開發者工具強制取消勾選也會被復原。
  `chat` 的子功能（附件、PPTX 匯出）仍可獨立關閉。
  （2026-07-21 追加 `quick_question`；現行政策本就啟用，行為不變、不需重新打包 EXE。）
- 測試中發現並修正：`list_documents`／`list_sessions` 回傳 list，閘門原本一律回錯誤 dict，
  會讓前端 `documents.forEach(...)` 拋例外；已改為被擋時回空 list，安靜降級。
- 獨立產生器網頁 `tools/feature-policy-editor.html`（單檔離線、不隨 App 發布），實測 13 個開關與
  上下層連動正確。管理者改用 `tools/open-feature-policy-editor.bat` 啟動時，會自動載入根目錄的
  `feature-policy.json`，修改後經嚴格驗證並原子覆蓋同一檔案；打包仍由管理者手動執行。
- **政策編譯進 PYZ 封存**：原先把 `feature-policy.json` 放進 `datas`，實測發現 onedir 的
  `_internal\` 是一般資料夾、該檔可被直接改寫（實際改寫成功），等於沒鎖。已改由
  `ClaudeCat.spec` 建置時產生 `config/_baked_policy.py` 隨 PYZ 編譯，`dist` 內不再有政策明文。
  改政策 = 重新打包。**限制**：會解開 PyInstaller 封裝的人仍可取得；定位為部署控制而非資安機制。
- 新版 EXE 已建置（81.4 MiB，2026-07-22），實機啟動與隔離部署檢查通過；實際停用項目以
  同輪 `ClaudeCat_release-manifest.json` 為準。Claude／Codex limits 已開放，外部 URL／非核准模型
  會被公司設定覆寫。
- **可稽核發布流程（2026-07-22）**：新增 `tools/build-release.ps1`，完整 log 放在
  `build/release-logs/`，成功 manifest 放在 `dist/ClaudeCat_release-manifest.json`；記錄來源政策、
  私有部署設定與 EXE 的 SHA-256，不在 manifest 暴露端點。最終建置 92/92 測試及 8/8 發布驗證
  通過，包含一般 GUI 啟動煙霧；`dist/ClaudeCat` 為 81.4 MiB、2,667 個檔案。
- PyInstaller 建置期間仍須暫時產生 `config/_baked_policy.py` 與 `_baked_deployment.py` 供分析，
  但 spec 的結束清理與發布腳本 finally 雙重移除；本輪建置後確認兩檔皆不存在。
- SOP 簡報改由同一份政策檔驅動（`tools/sop-deck-gen.js`），關閉的功能不會出現在簡報；
  本次政策下自動從 17 頁減為 16 頁（移除「用量顯示」整頁與相關註腳）。
- 開發過程修正：系統匣以預設參數綁值的 3 參數 lambda 會被 pystray 的 `_assert_action` 拒絕，
  導致啟動即死；已改為閉包工廠，8 秒啟動煙霧測試通過。

## v6.2 桌面 AI 工具箱（2026-07-19）

- 新增 JSON 工具分頁：Format、Minify、Validate、搜尋、Copy、Tree View 與 JSONPath；全部由本機確定性程式處理，不呼叫 LLM。
- 翻譯分頁支援英文／繁中／簡中與來源／目標雙箭頭切換；保留一般、技術、商務、中英對照，以及程式碼／表格／術語表保護選項。
- 頂端模型選單直接列出預設模型與 fallback models；使用者選擇後一般聊天立即採用並保存，切換不會遺失其他選項。進階設定頁仍負責端點、Timeout 與任務對應。
- 新增任務模型路由：翻譯、文件、程式分析、錯誤分析與一般聊天可各自選模型，未設定時回退至模式對應或預設模型。
- API Key 不由 UI 管理；仍由公司安裝程序或使用者執行期設定檔提供，避免以未加密的 UI 欄位保存憑證。
- 桌寵右鍵選單已統一為快速提問、LLM 介面、文件助手、JSON 工具、翻譯、模型設定與排程的直接入口；Skin 與桌寵設定維持子選單，移除重複的 Plugins 選單。
- 用量徽章同時顯示 Claude／Codex 時改為上下兩行，避免徽章過寬；Codex app-server 的安全錯誤訊息會直接顯示，便於判斷是否需要重新登入。
- 2026-07-19 第二輪人工驗收：拖曳位置持久化、點擊快速提問、Skin 切換持久化、排程 60 秒自動收合、用量 OFF 零請求、閒置睡眠／驚醒與所有工具頁停靠均通過。Esc 原回報經真正的 Windows `VK_ESCAPE` 驗證為工具注入限制造成的假陽性，保留輸入框 Esc 綁定作防禦性處理。另發現最大化工具頁關閉後桌寵會以縮小時座標還原而出界；已補啟動、拖曳、尺寸還原與徽章的夾邊（`_clamp_pet_position()`），同日人工複驗通過：開排程→最大化→關閉後桌寵落在 (1238,640)-(1366,768)，完整留在 1366x768 畫面內，徽章亦被夾住。
- 修正第三輪審查：文件檢索改用 CJK 詞組與最低相關門檻；長文件摘要／比較改為跨全文抽樣並明示非完整涵蓋；Word 表格與 Excel 欄標題會隨證據保留。翻譯以佔位符實際鎖定程式碼／SQL／識別碼，模型未完整保留即回報錯誤。
- 驗證：Python 3.11 `test_logic.py` **92/92** 通過（含管理政策直接覆蓋的嚴格驗證、公司端點／模型白名單、Workflow、文件、翻譯、排程與桌寵回歸）；`node --check frontend/chat.js`、`git diff --check`、打包文件／Workflow 與 8 秒 GUI 煙霧測試通過。實際內網語意品質仍待使用者環境確認。

### v6.2 尚待完成的實機項目

1. 在公司內網端點設定完成後，於「模型設定」頁執行 Health Check，並以實際文本確認翻譯結果與錯誤提示。
2. 已完成新版 EXE 打包與啟動煙霧測試：`dist\ClaudeCat\ClaudeCat.exe` 建置於 2026-07-19，啟動 5 秒仍存活；打包後 PDF／DOCX／PPTX／XLSX 文件驗證已通過。

### 核心桌面寵物（基底層）

| 模組 | 檔案 | 狀態 | 說明 |
|---|---|---|---|
| API 用量抓取 | api.py (251 行) | ✅ 完成 | 讀取 ~/.claude/.credentials.json OAuth token，呼叫 Anthropic 用量 API；含 429 退避、token 過期自動跑 claude update、model-scoped limits 合併 |
| 逐像素透明渲染 | winalpha.py (170 行) | ✅ 完成 | 純 stdlib ctypes 實作 UpdateLayeredWindow，取代色鍵去背（解決抗鋸齒洋紅毛邊）；含手刻 PNG 解碼（zlib/struct，無 Pillow） |
| 精靈圖載入 | spritecat.py (194 行) | ✅ 完成 | 載入 skins/ 下 PNG 精靈圖，去白背景、Pillow 縮放、翻轉朝向；支援 run/idle/sleep/error 四種姿勢自動分類 |
| 向量貓備用 | vectorcat.py (221 行) | ✅ 完成 | GDI+ 向量黑貓 8 幀跑步循環（已改用精靈圖，保留備援） |
| 主程式 | cat.py (842 行) | ✅ 完成 | tkinter 無邊框置頂視窗；動畫迴圈 + 輪詢迴圈雙線程；右鍵選單分組（設定收子選單）；含交談開/關貓縮放 + 貼齊視窗跟隨 |

### 已實作的使用者功能

- **用量驅動跑速**：0-25% 散步 → 25-50% 小跑 → 50-75% 快跑 → 75-95% 狂奔 → >95% 靜止
- **用量徽章**：貓下方顯示 Claude／Codex 的 session% + weekly% + 重置時間；同時啟用時上下兩行呈現，>90% 變紅警示
- **拖曳移動**：左鍵拖貓或徽章，位置於 Quit 時存入 config.json
- **右鍵選單**：狀態行 / 快速提問 / 交談（LLM 介面） / 文件助手 / JSON 工具 / 翻譯 / 模型設定 / 排程 / 切換 Skin / 寵物設定 / 測試 / 開啟記錄 / 結束
- **皮膚系統**：skins/ 下每個子資料夾為一組皮膚（bluecat / cowcat / ragdollcat），右鍵即時切換
- **多姿勢**：sleep / error / idle / run
- **設定持久化**：skin / 大小 / 朝向 / 置頂 / 輪詢間隔 / 位置，存於 %LOCALAPPDATA%\ClaudeCat\config.json
- **單實例保護**：Windows Named Mutex 防止重複執行
- **日誌系統**：RotatingFileHandler 3×512KB；右鍵 Show log 直接彈窗顯示
- **EXE 打包**：PyInstaller spec 檔已備妥（ClaudeCat.spec），skins/ 與 frontend/ 凍入

### Part 1 — 排程提醒 + 用量監控開關 ✅

| 項目 | 狀態 | 說明 |
|---|---|---|
| P1-0 pywebview+tkinter 共存驗證 | ✅ 完成 | 實測通過 |
| scheduler.py | ✅ 完成 | schedule.json 載入/驗證/寫回、tick() 三型判斷、lead/ontime 防重複 |
| cat.py 排程整合 | ✅ 完成 | 30 秒 tick、彈卡、alert 加速 3 秒 |
| 用量監控開關 | ✅ 完成 | ON/OFF 即時切換、OFF 真停輪詢、config 持久化 |
| 不可用偵測 | ✅ 完成 | 連續 3 次失敗或缺 token → 狀態轉變彈一次卡 |

### Part 1.5 — 基礎互動 ✅

| 項目 | 狀態 | 說明 |
|---|---|---|
| P1.5-1 拖曳 + 位置持久化 | ✅ 完成 | 拖曳已有，位置在 Quit 時存 |
| P1.5-2 點擊隨機小動作 | ✅ 完成 | 5px 位移閾值切分點擊/拖曳 |
| P1.5-3 素材包約定 + 角色子選單 | ✅ 完成 | skins/ 約定生效，右鍵隨選隨切 |
| P1.5-4 階段式睡眠 + 驚醒 | ✅ 完成 | 閒置計時，達 config sleep_min 後入睡 |

### Part 2 — LLM 交談 ✅

| 項目 | 狀態 | 說明 |
|---|---|---|
| P2-0~P2-2 LLM 設定與連通 | ✅ 完成 | vLLM 端點驗證通過 |
| P2-3 llm_service.py | ✅ 完成 | chat / probe / list_models / export / save_note |
| P2-4 config llm 區塊 | ✅ 完成 | llm.init(CONFIG_FILE) 讀取 |
| P2-5 前端交談頁 | ✅ 完成 | 模型下拉 / 對話區 / 輸入區 / Slash commands |
| P2-6 JsApi 橋接 | ✅ 完成 | send_message / sessions / export 等 |
| P2-7 貓縮放停靠 | ✅ 完成 | 開窗縮 32px + 貼齊跟隨 |
| P2-8 上下文管理 | ✅ 完成 | 動態 system prompt / 滑動視窗截斷 / context overflow |
| P2-9 文件匯出 | ✅ 完成 | chat_*.md / note_*.md |

---

## 今日修正（2026-07-17，實機測試中發現）

1. **視窗定位**：排除定位失效疑慮，修好徽章文字變寬後沒有重新置中的 bug。
2. **config.json 被靜默清空**：改為 read-merge-write，不再覆蓋 llm 區塊。
3. **LLM 端點曝露**：改成 _DEFAULTS 只留通用範例，真實設定只存 config.json。
4. **右鍵選單過寬**：狀態行縮短，設定項收進子選單。
5. **交談視窗與貓分離**：新增 _dock_tick() 貼齊跟隨。
6. **交談結束貓暴衝**：交談期間持續刷新閒置計時器。
7. **貓咪位置**：改為對齊視窗底部輸入區。
8. **模型幻覺預防**：system prompt 明確要求繁體中文、不編造。
9. **清除對話**：新增🗑️ 清除按鈕。
10. **思考狀態**：LLM 逾時延長至 180s，加入動態計時器。
11. **PPTX 生成**：落實 worker.py 解耦，支援 template.pptx 母片套用。
12. **PPT 轉檔崩潰**：修復 PyInstaller windowed 模式 stdio 為 None 的問題。
13. **Markdown 渲染**：程式碼區塊高亮 + 一鍵複製。
14. **Chatbot-UI 風格**：深色主題、Slash commands、程式碼複製、側邊欄；離線版不載入 highlight.js。
15. **歷史對話持久化**：Sessions 存於 %LOCALAPPDATA%\ClaudeCat\sessions\。
16. **exe 啟動即死**：修正 config/settings.py load_config() 忘了 return。
17. **MVC 重構殘留 `_settings` 未替換**：`cat.py` 殘存 `_settings.load_config()` 與
    `self._settings.save_config()` 導致 NameError 啟動即死，已全數替換為
    `settings.load_config()` 與 `self._save_config()`。
18. **chat.js 正規表達式斷行 Syntax Error**：`renderMarkdownLite()` 中的 RegExp
    literal 包含了真實的 LF 換行字元（`/```(.*?)[\n\n]+/`），導致整個 JS 檔案
    語法無效，pywebview 拒絕執行——表現為介面載入但按鈕全部無反應、模型選單空白、
    無法送出訊息。已修正為 `[\r\n]+` 跳脫寫法。
19. **前端全域錯誤捕捉**：新增 `window.onerror` 與 `unhandledrejection` 監聽器，
    未來若再有 JS 執行期錯誤將直接 alert 顯示，不再靜默。

---

## 未完成事項

### 驗收測試清單 🔲 未執行

**Part 1 驗收 (P1-8)**:
- [x] daily / lead_min / weekly / hourly 邏輯 *(test_logic.py + 實機)*
- [x] enabled=false / 刪除 / 格式錯誤 *(test_logic.py)*
- [o] 彈卡 60s 自動收合 *(視覺已確認，計時未驗)*
- [ ] 排程運作期間貓不掉幀
- [ ] 用量 OFF 後 log 零 API 請求、貓恆速
- [x] credentials 異常偵測與恢復 *(test_logic.py)*

**Part 1.5 驗收 (P1.5-5)**:
- [o] 拖放位置持久化 *(間接驗證)*
- [ ] 點擊即時反應
- [ ] 切換皮膚立即換幀
- [ ] 睡眠 → 驚醒兩階段

**Part 2 驗收 (P2-10)**:
- [ ] 聊天期間貓不掉幀；端點離線錯誤明確顯示
- [ ] 中文選字 Enter 不誤送；視窗單例
- [ ] 匯出/存檔內容正確；關窗貓復原
- [ ] **回歸：P1-8 全數重跑通過**

### Part 3 — 候選池（不承諾）

- ✅ P2-11 📎 檔案附加當 context（已實作）
- Mini mode / SSE 串流 / 跨 session 記憶 / Agent 委派 / 排程貪睡

---

## 檔案清單

```
claude-cat/  （2026-07-17 MVC 重構後結構）
├── cat.py            # 842 行  ✅ 主程式
├── api.py            # 251 行  ✅ Anthropic OAuth 用量 API
├── scheduler.py      #          ✅ 排程引擎
├── spritecat.py      #          ✅ 精靈圖載入
├── winalpha.py       #          ✅ 逐像素 alpha 渲染
├── vectorcat.py      #          ✅ 向量貓（備用）
├── worker.py         # 115 行  ✅ 子行程隔離重依賴
├── backend/
│   ├── window_main.py       # 141 行 ✅ pywebview 單例視窗
│   ├── routes/api.py        # 256 行 ✅ JsApi 橋接
│   ├── services/llm_service.py # 319 行 ✅ LLM 客戶端
│   └── prompts/system.txt   #        ✅ system prompt
├── frontend/
│   ├── index.html    #          ✅ 雙欄 Chatbot-UI
│   ├── chat.js       # 414 行  ✅ 前端邏輯 + 全域錯誤捕捉
│   └── style.css     #          ✅ 深色主題
├── config/settings.py # 47 行  ✅ 路徑與設定集中管理
├── skins/            # ✅ bluecat / cowcat / ragdollcat
├── ClaudeCat.spec    # ✅ PyInstaller onedir 打包配置
```

## 進度摘要

| 階段 | 進度 | 備註 |
|---|---|---|
| 核心桌面寵物 | ✅ 100% | 可獨立運作 |
| Part 1 排程+監控 | ✅ 100% | 待實機驗收剩餘項 |
| Part 1.5 基礎互動 | ✅ 100% | 待實機驗收 |
| Part 2 LLM 交談 | ✅ 100% | 待實機驗收 |
| MVC 重構 | ✅ 100% | 前後端分離完成 |
| Part 3 候選池 | 🔲 0% | 不承諾 |
