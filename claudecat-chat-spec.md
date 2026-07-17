# ClaudeCat 專案規格 v5.7（微服務解耦版）

> 交接文件。讀者是未來的 AI／Claude Code session。
> 前身：ClaudeCat 方案 A（fork usage-monitor-for-claude 的 api.py ＋ tkinter 桌面貓，RunCat 32px 幀圖放大至 96px）。
> v5 變更：全案重整為兩大部分——**Part 1 貓基本功能**（動畫＋用量監控開關＋排程提醒）、
> **Part 2 LLM 交談**（OpenAI 相容端點聊天入口）。Part 1 優先開發，驗收通過才啟動 Part 2。
> v5.1~v5.5：架構與互動定案（Windows 唯一平台、階段式睡眠、點擊分級）。
> v5.6 變更：新增「📎 檔案附加當 context」設計。
> v5.7 變更：確立**架構解耦（Option B）**——為解決引入 `pandas/numpy` 解析 Excel 導致主程式暴增破百 MB 的問題，決議未來將 LLM 通訊與檔案解析功能抽離為主程式之外的「子行程 / 獨立 DLL」，讓 `ClaudeCat.exe` 本體恢復為極輕量的桌面元件。

---

# Part 1 — 貓基本功能

**定位**：純 Windows 本機功能，不依賴任何 LLM。涵蓋桌面動畫、用量監控（可開關）、排程提醒。

## 1.1 需求

### 桌面動畫（既有，不動）

- RunCat 幀圖 96px、透明置頂、tkinter `after()` 迴圈換幀

### 用量監控開關

1. 右鍵選單勾選項「用量監控」，狀態存 config.json（`usage_monitor.enabled`），即點即存、重啟保留
2. **ON**：輪詢 Anthropic rate limit，跑速反映用量（既有行為）
3. **OFF**：**真停輪詢**（不打 API，非僅隱藏），貓固定悠閒速度
4. **不可用提醒**：credentials 缺失／token 讀取失敗／API 連續失敗 3 次 → 判「不可用」：
   - **狀態轉變時彈一次**小卡明說原因，不逐次輪詢洗版
   - 異常期間：貓慢速、選單項顯示「用量監控（異常）」
   - 恢復可用：自動回正常，不再提醒

### 排程提醒（與 LLM 完全無關，純確定性程式邏輯）

1. 三種週期：**每天**（time）、**每星期**（day＋time）、**每小時**（minute）
2. 每筆可設提前警示 `lead_min`；**提前＋正點各彈一次**（lead_min=0 只彈正點）
   例：09:00 開會、lead_min=10 → 08:50「10 分鐘後：開會」、09:00「現在：開會」
3. 彈窗：tkinter Toplevel 小卡——置頂、貓旁彈出、點擊關閉、60 秒自動收合、無貪睡
4. 彈窗同時貓切 alert 姿勢（無 alert 幀則跑速加快 3 秒示意）
5. 管理介面：**webview 表單**（pywebview 單例視窗的「排程」分頁）；右鍵選單「排程」直開該分頁
6. 錯過不補：關機期間過期的排程直接跳過

## 1.2 技術決策

| 項目 | 決策 | 理由 |
|---|---|---|
| 排程資料 | 獨立 `schedule.json` | 頻繁增刪，與程式設定分離 |
| 觸發引擎 | 掛貓的 `after()` 迴圈，每 30 秒 tick | 零新執行緒；分鐘級精度足夠 |
| 防重複 | 每筆記 `last_fired_lead`/`last_fired_ontime`（日期＋時刻粒度） | 30 秒輪詢同一分鐘多次命中 |
| 彈卡 | tkinter Toplevel（不用 webview） | 輕量提示不值得開 WebView2 |
| 管理介面 | pywebview 單例窗分頁表單，**即改即存** | 使用者定案；免批次儲存的狀態不一致 |
| 執行緒模型 | pywebview 佔主執行緒，tkinter 貓跑背景執行緒 | 待 P1-0 實機驗證 |
| 監控 OFF | api.py 輪詢真停 | 省資源＋語意誠實 |
| 不可用提醒 | 狀態轉變觸發一次，復用排程彈卡 | 失敗必須明說，但不洗版 |

### schedule.json 格式

```json
[
  { "id": "s1", "title": "開會", "type": "daily",
    "time": "09:00", "lead_min": 10, "enabled": true },
  { "id": "s2", "title": "週報", "type": "weekly",
    "day": "MO", "time": "16:00", "lead_min": 30, "enabled": true },
  { "id": "s3", "title": "喝水", "type": "hourly",
    "minute": 0, "lead_min": 0, "enabled": true }
]
```

`type`: daily｜weekly｜hourly；`day`: MO~SU（週型限定）；`lead_min`: 0＝只正點。

## 1.3 檔案結構（Part 1 範圍）

```
claude-cat/
├── api.py           # 小改：輪詢可停/可啟、失敗計數回報狀態
├── main.py          # 修改：右鍵選單（排程／用量監控勾選）、30秒 tick 掛入 after()、
│                    #   彈卡函式、貓 alert/慢速/悠閒速度切換
├── scheduler.py     # 新增：schedule.json 載入/驗證/寫回、tick(now)、防重複
├── config.json      # 新增：usage_monitor.enabled
├── schedule.json    # 新增：排程資料
└── chat/
    ├── window.py    # 新增：pywebview 單例 + 排程 js_api（list/upsert/delete）
    └── chat.html    # 新增：Tab 骨架（排程頁實作；交談頁留空殼給 Part 2）
```

## 1.4 待辦

**前置驗證（僅一項）**

- [ ] **P1-0. 跑 `verify_pywebview_tk.py`**，三項通過：tk 跳幀不卡／橋接 1 秒回傳／關 webview 後 tk 存活

**開發**

- [ ] P1-1. `scheduler.py`：載入/驗證（格式錯誤明說哪一筆，其餘照載）、tick 三型判斷、lead/ontime 防重複、寫回
- [ ] P1-2. `main.py`：30 秒 tick 掛入迴圈；彈卡（置頂/點關/60s 收合）；貓 alert 姿勢或加速 3 秒
- [ ] P1-3. `chat.html`：Tab 骨架＋排程頁（清單：title/週期摘要/enabled 開關/刪除；表單依 type 動態欄位）
- [ ] P1-4. `window.py`：pywebview 單例＋排程 js_api 三方法（即改即存）
- [ ] P1-5. 右鍵選單「排程」→ 開單例窗至排程分頁
- [ ] P1-6. 用量監控開關：config＋選單勾選；OFF 真停；失敗偵測（缺檔/token/連續3次）；
      狀態轉變彈一次卡；異常標示；自動恢復
- [ ] P1-7. 交談分頁空殼：Tab 可切但顯示「Part 2 未啟用」

**驗收（全過才進 Part 2）**

- [ ] P1-8. 測試清單：
  - daily：設 2 分鐘後＋lead_min=1 → 提前卡與正點卡各彈一次
  - lead_min=0 只彈正點；weekly 非當日不觸發；hourly 每小時該分鐘觸發
  - enabled=false／刪除後不觸發
  - schedule.json 改壞格式 → 明確指出錯誤筆，其餘正常
  - 彈卡 60s 自動收合；點擊即關；表單即改即存、重啟生效
  - 排程運作期間貓不掉幀
  - 用量開關：OFF 後 log 零 API 請求、貓恆速；改壞 credentials → 只彈一次異常卡＋選單（異常）；
    修復自動恢復不再彈；ON/OFF 重啟保留

---

# Part 1.5 — 基礎互動（Part 1 驗收後開發；與 Part 2 互不依賴，可並行）

**定位**：低成本高感知的貓互動。不引入手勢狀態機——只收「無判定衝突」的互動；
需要延遲判定或閾值切分的手勢（雙擊/長按等）全部延後。

## 1.5.1 需求

1. **拖曳**：按住貓拖動位置，放手落定；位置存 config，重啟復位
   （若現有實作已支援，本項改為驗證＋補存位置）
2. **點擊**：單擊貓 → 隨機小動作一種（跳一下／轉頭／喵字泡泡，實作擇一起步）；
   不與雙擊並存，故**無需延遲判定**，點擊即時反應
3. **右鍵切角色**：選單「角色」子選單列出可用素材包 → 切換即換幀圖組；
   選擇存 config，重啟保留
4. **閒置行為（階段式睡眠序列）**：無互動且（監控 OFF 或用量低）時漸進入睡——
   - 10 分鐘：想睡（跑速放最慢／打哈欠幀，素材缺則跳過此階段）
   - 12 分鐘：熟睡（睡覺幀；缺則靜止＋Zzz 泡泡）
   - **驚醒**：滑鼠移入貓範圍或點擊 → 驚醒小動作後回正常（缺驚醒幀則直接醒）
   - 用量突然跳動（監控 ON）亦喚醒
   階段時間存 config（`idle.doze_min: 10, sleep_min: 12`）；素材缺哪段就降級跳過哪段，不報錯

## 1.5.2 技術決策

| 項目 | 決策 | 理由 |
|---|---|---|
| 手勢範圍 | 只收點擊/拖曳——兩者以**位移閾值**（>5px 即拖曳）切分，無延遲判定 | 雙擊/長按需狀態機，延後 |
| 角色＝素材包 | 一個角色＝一組幀圖資料夾 `assets/<role>/`（含 run/idle 幀，alert/sleep 選配缺省降級） | 結構即約定 |
| 角色與人設 | **本階段只換外觀**；「切角色連動聊天人設（system prompt）」列 Part 2 選配，不在 1.5 | 1.5 無 LLM 依賴（假設待確認，見附錄 B-7） |
| 閒置判定 | 記最後互動時間戳，掛既有 30 秒 tick 順檢 | 零新迴圈 |

## 1.5.3 檔案結構（增量）

```
├── main.py          # 增：點擊/拖曳事件（位移閾值）、閒置計時、角色載入切換
├── config.json      # 增：role（當前角色）、position（貓座標）
└── assets/
    ├── black-cat/   # 既有 RunCat 幀重整為角色資料夾
    └── <其他角色>/   # 使用者自備素材包，照資料夾約定放入即被選單列出
```

## 1.5.4 待辦

- [ ] P1.5-1. 拖曳（或驗證既有）＋位置持久化
- [ ] P1.5-2. 點擊隨機小動作（位移閾值切分點擊/拖曳）
- [ ] P1.5-3. 素材包資料夾約定＋角色子選單＋切換與持久化；alert/sleep 幀缺省降級
- [ ] P1.5-4. 階段式睡眠（想睡→熟睡，config 可調時間）＋驚醒（滑鼠移入/點擊/用量跳動）；各階段素材缺省降級
- [ ] P1.5-5. 驗收：
  - 拖到任意位置放手，重啟後在原位
  - 點擊即時反應（無 300ms 遲滯感）；拖 3px 內視為點擊、超過為拖曳
  - 切角色立即換幀、重啟保留；素材缺 alert/sleep 幀時功能降級不報錯
  - 閒置依 config 時間漸進：想睡→熟睡兩階段可觀察；滑鼠移入觸發驚醒後回正常
  - 缺打哈欠/驚醒幀時階段自動跳過、不報錯；用量跳動（監控 ON）喚醒
  - 排程彈卡與用量監控在互動期間照常（回歸 P1-8 重點項）

---

# Part 2 — LLM 交談（Part 1 驗收通過後啟動）

**定位**：LLM 聊天入口。對接任一 **OpenAI 相容端點**（本機或區網皆可）。
**端點與模型設定由使用者另行提供**（base_url／model／必要時 api_key），提供前 Part 2 不啟動。

## 2.1 需求

1. 右鍵選單「交談」→ 開單例窗至交談分頁（填入 Part 1 預留空殼）；重複點選聚焦既有窗
2. 開窗時：貓縮 32px 停靠**固定角落**（定位一次，不跟隨拖動）；關窗恢復 96px 回原位
3. 視窗上下分割：上半對話記錄、下半輸入區
4. 頂部**模型下拉選單**：開窗 `GET /v1/models` 動態抓（兼作連通探測）；
   失敗 fallback config 清單並在對話區明說
5. 模型切換即時生效於下次請求、存回 config 當預設、**不清空 history**
6. 文件功能：「匯出對話」鈕＋每則回覆旁「💾 存檔」鈕；**寫檔永遠由使用者按鈕觸發**
7. 聊天期間用量輪詢與貓動畫照常（若監控 ON）

## 2.2 技術決策

| 項目 | 決策 | 理由 |
|---|---|---|
| LLM 協定 | OpenAI 相容 `/v1/chat/completions` | Ollama/LM Studio/llama.cpp/MLX 系通用，不綁 runtime |
| 端點 | 待使用者提供 `base_url`（含 `/v1`）；config 預留 `api_key` 欄位（本地端點通常留空） | 不綁特定機器/runtime |
| 回覆模式 | **不串流**；timeout 180s；等待「🐱 思考中... Xs」常駐計時，超過 180s 報錯中斷 | SSE 複雜度不值 v1；冷載入＋生成可 >30s |
| 送出防護 | 生成中鎖輸入；`event.isComposing` 防中文選字 Enter 誤送 | 中文使用者必踩雷 |
| history | 記憶體滑動視窗 `max_history_turns=10`；提供「🗑️ 清除」按鈕清空對話防幻覺；截斷印灰字 | 簡單優先 |
| 錯誤 | 連線失敗/逾時直接顯示對話區 | 失敗明說；LLM 掛不影響 Part 1 |
| 資料落地 | 對話 history／組裝後 prompt **不落地**；僅「匯出」與「💾」兩鈕寫檔；**debug log 預設關閉**，需 config 明設 `llm.debug_log: true` 才記 request/response，log 路徑寫死 `{export_dir}/debug/` | 不聲不響記對話是最差情況 |
| context 溢出 | 端點回 context 相關錯誤（HTTP 400 且訊息含 context/length/token）→ **自動砍半 history 重試一次**（10→5 輪），對話區灰字明說「內容過長，已縮短貓的記憶重試」；重試仍失敗 → 明確報錯不再重試 | 滑動視窗是估算防線，硬上限由端點裁決；降級要明說 |

### Prompt 與上下文

每次請求無狀態重組：

```python
messages = [
    {"role": "system", "content": build_system_prompt()},  # 動態生成
    *history,
    {"role": "user", "content": new_input}
]
```

System prompt：人設存 config `system_prompt`，程式注入即時用量；**監控 OFF/異常時注入狀態說明、不注入數值**：

```
你是 ClaudeCat，一隻住在桌面上的向量貓，平常負責監控主人的 Claude 用量。
回覆簡短（50 字內），口語自然。
目前狀態：session 用量 {X}%，weekly {Y}%，重置倒數 {Z}。
```

截斷：保留 system＋最近 10 輪，超過從最舊丟。N 預設保守值 10：多數本地部署無跨請求 KV cache（每輪重算 prefill），小模型 context 可能僅 4K-8K；實際端點確認後可依模型調整 `max_history_turns`。

**Context 溢出（兩道防線）**：
- 第一道＝滑動視窗（字數估算，擋大多數情況）；但單則超長輸入（如貼整段程式碼）仍可能突破
- 第二道＝端點錯誤降級：收到 context 類錯誤 → 砍半 history 重試一次並灰字明說；再失敗 → 報錯收手。
  原則：**寧可貓忘記，不可靜默截斷使用者剛貼的內容**——history 從最舊砍，最新輸入永不動。

### 檔案附加（📎）設計——已定規格，列 Part 3 候選（升級路徑：P2-11）

**用途定位**：ClaudeCat＝「資料縮減完之後的互動探索介面」——取代手動開網頁版貼資料的動作；
SQL 聚合與批次呼叫管線仍屬獨立腳本，兩者互補不替代。

| 項目 | 決策 | 理由 |
|---|---|---|
| 觸發 | 輸入區 📎 鈕 → 檔案選擇器；**LLM 不得自行讀檔案系統** | 與「寫檔按鈕觸發」原則對稱 |
| 格式白名單 | `.txt .md .csv .sql .log .xlsx .xls` | v5.7 決議加入 Excel 支援 |
| 大小上限 | config `llm.max_file_chars`（預設 20000 字）；超過**明說**「檔案內容過長...」，不靜默截斷 | 強制執行「先縮減再對話」紀律 |
| context 歸屬 | 檔案內容併入**該則最新輸入**、**不進 history 滑動視窗**（僅該輪有效） | 避免一個檔案吃光後續十輪記憶；溢出防線「砍 history 不砍最新輸入」現成接手 |
| 溢出 | 零 history＋檔案仍塞不下 → 誠實報錯，不硬塞 | 沿用 v5.2 兩道防線 |
| 端點彈性 | 若使用者提供的是大 context 端點（如內部 gateway），僅調 config 上限，架構不動 | 已預留 |

### 2.2.1 架構重構：LLM 功能微服務化（Option B 解耦策略）

**背景**：
為了實作上述的 `.xlsx` 解析，系統引入了 `pandas` 與 `openpyxl`，連帶拉入龐大的 `numpy` DLL。導致原本輕量級的桌面寵物 `ClaudeCat.exe` 體積從數十 MB 暴增破百 MB，每次啟動需在 `%TEMP%` 解壓縮巨量依賴，嚴重拖慢啟動速度與佔用硬碟。

**解耦實作 (Implemented in v5.8)**：
1. **主程式恢復輕量**：`ClaudeCat.exe` 只負責 UI（tkinter 動畫、排程管理、pywebview 介面呈現），完全排除 `pandas`、`numpy`、`python-pptx` 等重型科學運算與轉檔套件。打包改採 `onedir` 模式，主執行檔縮減至 ~23MB，DLL 皆抽離至 `_internal`。
2. **分離 Parser / LLM Worker**：
   - 將 Excel 解析與 PPTX 產生邏輯獨立拆分為 `worker.py`。
   - **通訊方式**：主程式透過 `subprocess` 呼叫 `ClaudeCat.exe --worker <file>` 來瞬間載入依賴並解析資料，或呼叫 `--ppt <file> <template>` 生成簡報。完成後 Worker 自動銷毀，釋放記憶體。
3. **PPTX 簡報生成 (v5.8 新功能)**：
   - 支援將 LLM 產生的 Markdown 大綱（包含 `# Slide`）轉為 `.pptx`。
   - 採用「先大綱後成品」流程，當對話包含簡報格式時，自動浮現「📽️ 匯出成 PPT」按鈕。
   - 支援母片套用：優先尋找執行檔同目錄的 `template.pptx`，找不到則退回尋找 `%LOCALAPPDATA%\ClaudeCat\template.pptx`。

## 2.3 環境前提（LLM 端點側）

由使用者提供設定時一併確認：

1. **端點可達**：從跑 ClaudeCat 的 Windows 可連到 `base_url`（本機 localhost 或區網 IP 皆可）
2. **協定相容**：支援 `/v1/chat/completions` 與 `/v1/models`（Ollama／LM Studio／llama.cpp server／MLX 系皆符合）
3. **若端點在另一台機器**：該機需監聽 `0.0.0.0`（非僅 localhost）、防火牆放行、不睡眠
4. 模型冷載入可能 10-30 秒 → timeout 60s＋開窗暖機探測涵蓋（與端點種類無關，設計已包含）

## 2.4 檔案結構（Part 2 增量）

```
├── llm.py           # 新增：chat(messages)（timeout 60s）+ list_models()，錯誤明確拋出
├── config.json      # 增：llm { base_url, model, system_prompt,
│                    #          max_history_turns: 10, fallback_models: [], export_dir }
└── chat/
    ├── window.py    # 增：暖機探測＋聊天 js_api（send/list_models/set_model/save_file/export_chat），
    │                #   LLM 呼叫跑 thread 不卡 UI
    └── chat.html    # 增：交談頁實作（模型下拉/對話區＋💾＋截斷灰字/輸入區/匯出鈕）
```

## 2.5 待辦

**前置驗證**

- [ ] P2-0. **使用者提供 LLM 設定**：base_url／model／api_key（若需）——此為 Part 2 的啟動閘門
- [ ] P2-1. 端點側環境確認（見 2.3；端點在本機則僅需服務啟動）
- [ ] P2-2. Windows curl 連通並確認 model id：
  ```
  curl http://<IP>:<port>/v1/models
  curl http://<IP>:<port>/v1/chat/completions -H "Content-Type: application/json" -d "{\"model\":\"<模型名>\",\"messages\":[{\"role\":\"user\",\"content\":\"hi\"}]}"
  ```

**開發**

- [ ] P2-3. `llm.py`
- [ ] P2-4. config llm 區塊
- [ ] P2-5. `chat.html` 交談頁（isComposing、送出鎖、🐱…、💾、匯出）
- [ ] P2-6. `window.py` 暖機探測＋聊天 js_api（thread）
- [ ] P2-7. `main.py`：「交談」選單→開窗＋貓縮放停靠；關窗復原
- [ ] P2-8. 上下文：動態 system prompt（含監控狀態分支）、滑動視窗截斷、context 溢出降級（砍半重試一次＋灰字提示）
- [ ] P2-9. 文件：匯出 `chat_YYYYMMDD_HHMMSS.md`；💾 存 `note_YYYYMMDD_HHMMSS.md`（皆含時間戳、模型）

**驗收**

- [ ] P2-10. 測試清單：
  - 貓聊天期間不掉幀；端點離線/斷線錯誤明確顯示；開窗即知 LLM 離線
  - 中文選字 Enter 不誤送；生成中重按無效；單例
  - 模型 fallback 提示正確；切模型 history 保留
  - 監控 OFF 時聊天 prompt 注入狀態說明（貓不拿舊數字胡說）
  - 匯出/存檔內容正確；關窗貓復原
  - debug_log 預設關閉時 {export_dir}/debug/ 不產生任何檔；設 true 後有記錄
  - 貼超長文字觸發 context 錯誤 → 觀察到灰字降級提示與重試；極端長度下最終報錯不無限重試
  - **回歸：P1-8 全數重跑通過**（交談開發不得弄壞 Part 1）

---

# 共用附錄

## A. 已否決／延後（避免重議）

| 項目 | 處置 | 理由 |
|---|---|---|
| `chrome --app=` 模式 | 否決 | 依賴 Chrome、生命週期難控 |
| 整包改 Electron | 否決 | 等於重寫 |
| desktop-fox provider registry | 否決 | 本地 LLM 全講 OpenAI 格式 |
| xai-org/grok-build | 否決 | 終端 coding agent（Rust TUI），非可嵌元件；認證綁 x.ai |
| 跨 session 聊天記憶（SQLite） | 延後 | 關窗即忘；要加只是 list 換讀寫檔 |
| SSE 串流 | 延後 | timeout 60s＋等待提示先擋 |
| 貓跟隨視窗拖動 | 否決 | 需輪詢視窗座標，複雜度不值 |
| Agent 委派（claude -p headless） | 延後 | 走雲端額度，偏離 local LLM 初衷 |
| AI 客服入口 | 排除 | 屬 erp-llm-v2 前端專案；僅可複用 llm.py 概念 |
| 排程貪睡（snooze） | 延後 | 點關＋自動收合先擋 |
| 排程錯過補償通知 | 否決 | 複雜度陷阱 |
| 排程接 LLM（智慧文案） | 否決 | 確定性工作不經過 LLM |
| 手編 JSON 排程管理 | 否決 | 定案 webview 表單 |
| Fork BongoCat（Tauri/Rust+Vue） | 否決 | 鍵盤反應寵目的錯位；雙棧學習成本最高；改造量≈全部 |
| Fork TonyNa desktop-pet（Electron） | 否決（保留為設計參考） | 手勢/角色包功能雖現成，但 3 星專案品質與授權未確認、Electron 體重、api.py 需重寫 TS；棄置既有 Python 成果 |
| 跨平台（macOS/Linux） | 暫停評估 | Windows 為主角；僅於未來開源上 GitHub 時重啟（tkinter 透明視窗與 pywebview 底層在 macOS 行為不同，屆時渲染層約 30-40% 移植量） |
| 雙擊/長按/懸停/滾輪/甩動/游標追蹤 | 延後（Part 3 候選） | 需手勢狀態機或系統級 hook，等 Part 1/2 落地再議；clawd-on-desk 證明雙擊/連擊分級在桌寵可行（但其為 Electron/DOM 事件體系，tkinter 需自刻狀態機），「單擊即時、雙擊延後」定案不變 |
| Mini mode（拖至螢幕邊緣縮進、懸停探頭） | 延後（Part 3 候選，源自 clawd-on-desk） | 概念比「縮小停靠聊天窗」更通用；需邊緣偵測＋懸停判定，等基礎互動落地 |
| 📎 檔案附加當 context（含 drop file 投餵） | 延後（Part 3 候選，**規格已定於 2.2 節，可直升 P2-11**） | Part 2 已有 10 項待辦，先讓貓開口說話；設計已凍結，升級零重議 |
| .xlsx 直接解析 | 否決 | EBS 匯 CSV 即可，省 openpyxl 依賴 |
| 批次調度／自動化管線（大量資料分批送 LLM 寫回） | 排除 | 屬獨立腳本職責；ClaudeCat 僅為縮減後資料的互動探索介面 |
| clawd-on-desk 程式碼抄用 | **禁止** | AGPL-3.0 具傳染性——未來若開源，抄用將迫使本專案 AGPL；**僅允許概念層參考** |
| agent 狀態 hooks 整合（clawd-on-desk 路線） | 否決 | 資料源不同（agent 事件流 vs 額度 API）；該需求直接安裝 clawd-on-desk 即可（支援 Hermes Agent），兩寵各司其職 |
| window sitting（貓坐視窗標題列） | 否決 | 需輪詢全系統視窗座標，成本最高 |
| 多寵互動 | 否決 | 使用場景不存在 |

## B. 核心假設（錯了要重評計劃）

1. pywebview + tkinter 執行緒共存在 Windows 可行 → P1-0（**兩部共同前置**）
2. 現有貓本體是 tkinter（若是 pygame，P1-2／P2-7 做法要改）
3. 30 秒輪詢的分鐘級精度可接受（排程不承諾秒級準時）
4. 使用者將提供 OpenAI 相容端點設定；提供前 Part 2 凍結 → P2-0（僅 Part 2）
5. 該端點支援 `/v1/chat/completions` 與 `/v1/models` → P2-2 驗證（僅 Part 2）
6. 本地小模型 context 保守估 4K-8K、無跨請求 KV cache → 10 輪上限與不串流；端點確認後可調（僅 Part 2）
7. 「切角色」僅換外觀素材、不連動聊天人設（**待使用者確認**；若要連動，Part 2 的 system_prompt 需改為每角色一份）

## C. 成功標準

**Part 1**：右鍵新增排程「daily 09:00 開會 lead_min=10」→ 08:50 與 09:00 各彈一次卡、貓示警、點卡即關；
關閉用量監控 → 零 API 請求、貓恆速；credentials 壞掉 → 只提醒一次、修復自動恢復。全程貓不掉幀。

**Part 1.5**：拖曳定位重啟不跑位；點擊即時小動作；右鍵切角色即換裝且重啟保留；閒置入睡、互動即醒。

**Part 2**：右鍵「交談」→ 貓縮小停靠 → 開窗即列模型 → 中文輸入不誤送 → 60 秒內回覆 →
💾 產出實體 .md → 關窗貓復原 → Part 1 功能回歸全過。

全程無靜默失敗。
