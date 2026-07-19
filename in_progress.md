# ClaudeCat 進度報告

> 產生時間：2026-07-17（同日多次更新，見「今日修正」）
> 對應 spec：claudecat-chat-spec.md v5.6
> 對應 TODO：todo.md

---

## 已完成功能總覽

## v6.2 桌面 AI 工具箱（2026-07-19）

- 新增 JSON 工具分頁：Format、Minify、Validate、搜尋、Copy、Tree View 與 JSONPath；全部由本機確定性程式處理，不呼叫 LLM。
- 新增英／繁中翻譯分頁：一般、技術、商務、中英對照，以及程式碼／表格／術語表保護選項。
- 頂端模型選單改為一般使用者可理解的模式（自動、快速、高品質、程式分析、翻譯）；進階設定頁才可修改端點、模型、Timeout、模式與任務對應。
- 新增任務模型路由：翻譯、文件、程式分析、錯誤分析與一般聊天可各自選模型，未設定時回退至模式對應或預設模型。
- API Key 不由 UI 管理；仍由公司安裝程序或使用者執行期設定檔提供，避免以未加密的 UI 欄位保存憑證。
- 桌寵右鍵選單已統一為快速提問、LLM 介面、文件助手、JSON 工具、翻譯、模型設定與排程的直接入口；Skin 與桌寵設定維持子選單，移除重複的 Plugins 選單。
- 用量徽章同時顯示 Claude／Codex 時改為上下兩行，避免徽章過寬；Codex app-server 的安全錯誤訊息會直接顯示，便於判斷是否需要重新登入。
- 修正第三輪審查：文件檢索改用 CJK 詞組與最低相關門檻；長文件摘要／比較改為跨全文抽樣並明示非完整涵蓋；Word 表格與 Excel 欄標題會隨證據保留。翻譯以佔位符實際鎖定程式碼／SQL／識別碼，模型未完整保留即回報錯誤。
- 驗證：Python 3.11 `test_logic.py` **51/51** 通過（含本機 OpenAI-compatible 假端點、中文誤命中、抽樣涵蓋、sidecar 路由、JSON 深度、翻譯還原、weekly 非當日、disabled/delete 排程與 worker 分頁／截斷）；`node --check frontend/chat.js` 與 `git diff --check` 通過。翻譯／Health Check 的實際內網端點連線待使用者環境確認。文件助手已確認採公司內網 endpoint；不再將「完全離線推論」列為驗收阻塞。

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
