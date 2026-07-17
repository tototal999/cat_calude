# ClaudeCat 進度報告

> 產生時間：2026-07-17
> 對應 spec：claudecat-chat-spec.md v5.6
> 對應 TODO：todo.md

---

## 已完成功能總覽

### 核心桌面寵物（基底層）

| 模組 | 檔案 | 狀態 | 說明 |
|---|---|---|---|
| API 用量抓取 | api.py (251 行) | ✅ 完成 | 讀取 ~/.claude/.credentials.json OAuth token，呼叫 Anthropic 用量 API；含 429 退避、token 過期自動跑 claude update、model-scoped limits 合併 |
| 逐像素透明渲染 | winalpha.py (170 行) | ✅ 完成 | 純 stdlib ctypes 實作 UpdateLayeredWindow，取代色鍵去背（解決抗鋸齒洋紅毛邊）；含手刻 PNG 解碼（zlib/struct，無 Pillow） |
| 精靈圖載入 | spritecat.py (194 行) | ✅ 完成 | 載入 skins/ 下 PNG 精靈圖，去白背景、Pillow 縮放、翻轉朝向；支援 run/idle/sleep/error 四種姿勢自動分類 |
| 向量貓備用 | vectorcat.py (221 行) | ✅ 完成 | GDI+ 向量黑貓 8 幀跑步循環（已改用精靈圖，保留備援） |
| 主程式 | cat.py (~740 行) | ✅ 完成 | tkinter 無邊框置頂視窗；動畫迴圈 + 輪詢迴圈雙線程；右鍵選單完整；含交談開/關貓縮放 |

### 已實作的使用者功能

- **用量驅動跑速**：0-25% 散步 → 25-50% 小跑 → 50-75% 快跑 → 75-95% 狂奔 → >95% 靜止
- **用量徽章**：貓下方顯示 session% + weekly% + 重置時間，>90% 變紅警示
- **拖曳移動**：左鍵拖貓或徽章，位置於 Quit 時存入 config.json
- **右鍵選單**：狀態行 / Refresh now / Always on top / Show usage % / 用量監控 / 排程... / 交談... / Size / Refresh 間隔 / Skin / Face right / Test / Show log / Quit
- **皮膚系統**：skins/ 下每個子資料夾為一組皮膚（bluecat / cowcat / ragdollcat），右鍵即時切換
- **多姿勢**：sleep（session 100% 睡覺）、error（API 錯誤時）、idle（>95% 待命）、run（一般跑步）
- **設定持久化**：skin / 大小 / 朝向 / 置頂 / 輪詢間隔 / 位置，存於 %LOCALAPPDATA%\ClaudeCat\config.json
- **單實例保護**：Windows Named Mutex 防止重複執行
- **日誌系統**：RotatingFileHandler 3×512KB；右鍵 Show log 直接彈窗顯示（不依賴 Explorer）
- **EXE 打包**：PyInstaller spec 檔已備妥（ClaudeCat.spec），skins/ 凍入但支援外部覆蓋

### Part 1 — 排程提醒 + 用量監控開關

| 項目 | 狀態 | 說明 |
|---|---|---|
| P1-0 pywebview+tkinter 共存驗證 | ✅ 完成 | 實測通過 |
| scheduler.py | ✅ 完成 | schedule.json 載入/驗證/寫回、tick() 三型判斷、lead/ontime 防重複 |
| cat.py 排程整合 | ✅ 完成 | 30 秒 tick、彈卡、alert 加速 3 秒 |
| 用量監控開關 | ✅ 完成 | ON/OFF 即時切換、OFF 真停輪詢、config 持久化 |
| 不可用偵測 | ✅ 完成 | 連續 3 次失敗或缺 token → 狀態轉變彈一次卡 |
| chat/window.py | ✅ 完成 | pywebview 單例 + 排程 js_api + 聊天 js_api |
| chat/chat.html | ✅ 完成 | Tab 骨架 + 排程頁 + 交談頁 |
| 右鍵「排程...」「交談...」 | ✅ 完成 | 開啟 pywebview 單例窗至對應分頁 |

### Part 1.5 — 基礎互動

| 項目 | 狀態 | 說明 |
|---|---|---|
| P1.5-1 拖曳 + 位置持久化 | ✅ 完成 | 拖曳已有，位置在 Quit 時存 |
| P1.5-2 點擊隨機小動作 | ✅ 完成 | 5px 位移閾值切分點擊/拖曳；點擊觸發加速 sprint 小動作 |
| P1.5-3 素材包約定 + 角色子選單 | ✅ 完成 | skins/ 約定生效，右鍵隨選隨切 |
| P1.5-4 階段式睡眠 + 驚醒 | ✅ 完成 | 閒置計時 (hover/click/用量跳動喚醒)，達 config sleep_min 後入睡 |

### Part 2 — LLM 交談

**LLM 設定**（P2-0 ✅ 已提供）：
```
base_url:  http://example.invalid:8000/LLM/v1
model:     Qwen/Qwen3.6-35B-A3B-FP8-nothink
api_key:   (不需要)
engine:    vLLM 0.25.0
```

**注意**：`/v1/models` 端點回 404，模型下拉改從 config `fallback_models` 靜態清單讀取。

| 項目 | 狀態 | 說明 |
|---|---|---|
| P2-0 使用者提供 LLM 設定 | ✅ 完成 | 已驗證端點連通 |
| P2-1 端點連通測試 | ✅ 完成 | chat completions 正常回應 |
| P2-2 curl 連通測試 | ✅ 完成 | /v1/models 404 → 改用 config 靜態清單 |
| P2-3 llm.py | ✅ 完成 | chat / probe / list_models / export / save_note / debug_log |
| P2-4 config llm 區塊 | ✅ 完成 | llm.init(CONFIG_FILE) 讀取 llm block |
| P2-5 chat.html 交談頁 | ✅ 完成 | 模型下拉 / 對話區+💾 / 輸入區 isComposing+送出鎖 / 🐱… / 匯出鈕 |
| P2-6 window.py 聊天 js_api | ✅ 完成 | send_message / list_models / set_model / save_note / export_chat / probe |
| P2-7 貓縮放停靠 | ✅ 完成 | 開窗縮 32px / 關窗復原原始大小 |
| P2-8 上下文管理 | ✅ 完成 | 動態 system prompt 注入用量狀態 / 滑動視窗截斷 / context overflow 砍半重試+灰字 |
| P2-9 文件匯出 | ✅ 完成 | export_chat → chat_*.md / save_note → note_*.md |
| P2-10 驗收 | 🔲 未執行 | 需實機測試 |

---

## 未完成事項

### 驗收測試清單 🔲 未執行

**Part 1 驗收 (P1-8)**:
- [x] daily：設 2 分鐘後 + lead_min=1 → 提前卡與正點卡各彈一次
      *(✅ test_logic.py 邏輯驗證 + 2026-07-17 實機跑：08:51 lead、08:52 ontime 各觸發一次)*
- [x] lead_min=0 只彈正點；weekly 非當日不觸發；hourly 每小時該分鐘觸發 *(✅ test_logic.py)*
- [x] enabled=false / 刪除後不觸發 *(✅ test_logic.py)*
- [x] schedule.json 改壞格式 → 明確指出錯誤筆，其餘正常 *(✅ test_logic.py)*
- [o] 彈卡 60s 自動收合；點擊即關；表單即改即存、重啟生效
      *(2026-07-17 實機看過彈卡外觀正常出現；60s 自動收合未計時驗證、表單存檔未逐項測)*
- [ ] 排程運作期間貓不掉幀 *(需實機測試)*
- [ ] 用量 OFF 後 log 零 API 請求、貓恆速 *(需實機測試)*
- [x] 改壞 credentials → 只彈一次異常卡 + 選單（異常）；修復自動恢復；ON/OFF 重啟保留
      *(✅ test_logic.py 邏輯驗證；真憑證損壞情境未實機測)*

**視窗定位 bug（2026-07-17 已結案）**：
Part 1 執行緒重構後（pywebview 主執行緒 + tk 背景執行緒）一度懷疑貓/徽章定位失效。
用兩組固定座標 (1100,420) / (300,250) 實機驗證：`tkinter` 回報值與 Windows
`GetWindowRect` 皆精準命中，**現行版本未重現**。過程中另外抓到並修好一個真 bug：
徽章文字寬度變化時（`...` → `64% W70% | 17:00`）沒有重新置中，導致長期偏移貓中軸
——已改為文字內容變化時才重新置中（維持先前 DWM 效能修正，不影響每幀效能）。

**Part 1.5 驗收 (P1.5-5)**:
- [o] 拖到任意位置放手，重啟後在原位
      *(2026-07-17 已用固定座標間接驗證定位機制正確；未做「手動拖曳→重啟」全流程)*
- [ ] 點擊即時反應加速，無遲滯感
- [ ] 切換皮膚/角色立即換幀
- [ ] 閒置不動達設定時間後進入睡眠狀態；游標滑過或點擊即刻醒來

### Part 2 — 驗收測試（P2-10）🔲 未執行

- [ ] 聊天期間貓不掉幀；端點離線錯誤明確顯示；開窗即知離線
- [ ] 中文選字 Enter 不誤送；生成中重按無效；視窗單例
- [ ] 模型 fallback 提示正確；切模型 history 保留
- [ ] 監控 OFF 時 prompt 注入狀態說明（貓不拿舊數字胡說）
- [ ] 匯出/存檔內容正確；關窗貓復原
- [ ] debug_log 預設關閉時零檔案；設 true 有記錄
- [ ] 貼超長文字 → 灰字降級提示與重試；極端長度最終報錯
- [ ] **回歸：P1-8 全數重跑通過**

### Part 3 — 候選池（不承諾）

- 📎 檔案附加當 context（規格已定，可直升 P2-11）
- Mini mode（拖至邊緣縮進、懸停探頭）
- 雙擊/長按/懸停/滾輪/甩動/游標追蹤（需手勢狀態機）
- SSE 串流回覆
- 跨 session 聊天記憶
- 切角色連動聊天人設
- Agent 委派（claude -p headless）
- 排程貪睡（snooze）

---

## 📌 待使用者決定

- [x] ~~LLM 設定~~ → 已提供 (example.invalid:8000)
- [ ] 切角色是否連動聊天人設（Part 2 驗收後定案即可）
- [ ] 📎 檔案附加要不要直升 P2-11（Part 2 驗收後定案即可）

---

## 檔案清單

```
claude-cat/
├── api.py            # 251 行  ✅ Anthropic OAuth 用量 API 客戶端
├── cat.py            # ~740 行 ✅ 主程式（含交談開/關貓縮放 + 用量狀態注入）
├── llm.py            # ~240 行 ✅ LLM 客戶端（chat/probe/export/debug_log）
├── spritecat.py      # 194 行  ✅ 精靈圖載入
├── winalpha.py       # 170 行  ✅ UpdateLayeredWindow 逐像素 alpha 渲染
├── vectorcat.py      # 221 行  ✅ GDI+ 向量貓（備用）
├── scheduler.py      # 208 行  ✅ 排程引擎
├── verify_pywebview_tk.py  # ✅ pywebview+tkinter 共存驗證腳本
├── chat/
│   ├── window.py     # ~190 行 ✅ pywebview 單例 + 排程 js_api + 聊天 js_api
│   └── chat.html     #         ✅ 排程頁 + 交談頁（完整實作）
├── skins/
│   ├── bluecat/      # ✅ 藍貓皮膚
│   ├── cowcat/        # ✅ 乳牛貓皮膚
│   └── ragdollcat/    # ✅ 布偶貓皮膚
├── frames/           # 舊版 RunCat365 素材（備用）
├── ClaudeCat.spec    # ✅ PyInstaller 打包配置
├── cat.md            # 需求文件
├── claudecat-chat-spec.md  # 專案規格 v5.6
├── todo.md           # 待辦清單
└── README.md         # 使用說明
```

## 進度摘要

| 階段 | 進度 | 備註 |
|---|---|---|
| 核心桌面寵物 | ✅ 100% | 可獨立運作 |
| Part 1 程式碼 | ✅ 100% | 排程 + 用量開關 + pywebview |
| Part 1 驗收 | 🔲 0% | P1-8 清單未逐項執行 |
| Part 1.5 基礎互動 | ✅ 100% | 程式碼已完成（點擊小動作/睡眠喚醒） |
| Part 2 程式碼 | ✅ 100% | P2-3~P2-9 全部完成 |
| Part 2 驗收 | 🔲 0% | P2-10 需實機測試 |
| Part 3 候選池 | 🔲 0% | 不承諾 |
