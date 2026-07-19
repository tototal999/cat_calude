# ClaudeCat v6.1 MVP：本機文件助手

更新日期：2026-07-18

## 目標與範圍

產品定位調整為「桌面寵物 + 本機文件助手」，不是雲端 ChatGPT 的複製版。使用者不需要另開 Ollama、命令列或模型視窗；預設推論使用使用者已接受的公司內網 OpenAI-compatible endpoint，本機 llama.cpp sidecar 僅保留為未來離線備援。

此 MVP 的兩個入口如下：

```text
🐱 嗨，我可以陪你聊天，也可以讀文件。

[聊聊天]  [拖文件給我]
```

1. **聊聊天**：預設使用公司內網 Qwen OpenAI-compatible endpoint；未來可選用隨安裝包提供的本機 GGUF／llama.cpp sidecar。
2. **拖文件給我**：開啟 AI 文件助手工作區；文件與索引留在使用者電腦，僅將檢索命中的必要段落與來源定位傳給公司內網 endpoint 產生回答。

簡單提問的預設互動是單擊桌面貓，開啟貼在貓旁的輕量輸入泡泡；按 Enter 即直接取得公司內網 Qwen 回答，不開完整聊天視窗。右鍵的「交談…」保留給多輪長對話。

第一版不做語音、多人共用知識庫、文件自動上傳、掃描 PDF OCR 或視覺辨識。偵測到沒有可擷取文字的掃描 PDF 時，必須明確提示「此掃描型 PDF 需先經 OCR 才能閱讀」。

## 文件助手流程

```text
拖入文件
  → MarkItDown sidecar 轉 Markdown
  → 保留頁面／章節／工作表 metadata
  → 本機切塊及檢索
  → 僅將相關段落交給設定的公司內網 LLM（或未來本機備援）
  → 回答、引用來源，或明確表示文件未提及
```

- 支援的首批來源：PDF、Word、Excel、PowerPoint、CSV、Markdown 與純文字。
- 每個區塊必須持久化 `document_id`、原始檔名、文字、標題階層及來源定位。
  - PDF：頁碼與頁內順序；不可只從轉換後 Markdown 反推頁碼。
  - Word：標題／章節、段落順序與表格列。
  - PowerPoint：投影片編號與標題。
  - Excel：工作表名稱、實際儲存格範圍與列／欄標題。
- 「只回答文件內容」預設開啟。回答只可依檢索到的區塊；缺少足夠證據時固定回覆：`此文件沒有描述此問題，無法依文件確認。`
- 引用由檢索結果的 metadata 產生，不得僅依 LLM 自行生成。例如：`採購流程.pdf · 第 8 頁 · 付款條款`。
- 工作區提供：摘要、問問題、流程／SOP、整理表格、比較文件，以及三個建議問題。超過上下文上限的摘要／比較採跨全文抽樣，必須在結果中明示「非完整文件結論」，不得假裝已涵蓋全部內容。

## 本機部署約束

- Python 3.10+、MarkItDown、其轉檔依賴、llama.cpp 相容 runtime 與量化 GGUF 模型，均由公司安裝包離線提供；執行期不得要求使用者下載或自行安裝套件。
- sidecar 僅監聽 `127.0.0.1` 的隨機／受控連接埠，不對區網公開；主程式停止時一併停止。
- 文件索引置於 `%LOCALAPPDATA%\ClaudeCat\documents\`；提供「從本機索引移除」操作，不刪除使用者原始檔案。
- 文件內容、提示詞、模型輸出與索引不得傳送到外網。診斷紀錄不得記錄文件全文。

## 推論與用量邊界

- 一般聊天與文件問答只使用設定於 `llm.base_url` 的公司內網 Qwen OpenAI-compatible endpoint。
- Claude／Codex limits 是與聊天／文件助手完全獨立的可選監控。兩個開關預設 OFF；一般聊天與文件問答不使用其登入憑證、CLI 或 app-server。
- Claude／Codex 開啟前都必須由該電腦使用者明確同意；若兩者皆未安裝或未登入，顯示 `No use` 且不發出查詢。Claude 開啟後輪詢既有 usage API；Codex 啟用後以本機 app-server 的 `account/rateLimits/read` 讀取用量，不直接讀取、顯示、保存或上傳 token；此為非官方相容方式，Codex 更新後可能失效。

## OpenPets-style 桌寵演進

保留 Python／Tkinter 與既有服務，不導入 Electron、Node.js 或 OpenPets 程式碼；只借用其本機優先、狀態驅動與可選模組的產品概念。

1. `PetState`：`IDLE → LISTENING → THINKING → STREAMING → SUCCESS / ERROR → IDLE`。
2. 單擊貓維持貼身輸入泡泡；短答留在泡泡，長答展開貼身卡片（複製、繼續問、收合），不開 WebView。
3. 後續才拆分 UI／服務／plugin 邊界；第一版不做動態下載插件或讓插件讀取 token、檔案、任意網路。

### 素材缺口（2026-07-18）

現有素材可安全 fallback：缺少專用動作時，`idle` 使用第一張 run 圖，`LISTENING`／`SUCCESS` 使用 idle，`THINKING`／`STREAMING` 使用 run，`ERROR` 沒有專用圖時保持一般動畫。若要完整呈現狀態機，請依下列命名補圖：`<skin>_<action>_<order>.png`。

| skin | 現有 | 建議補圖 |
|---|---|---|
| bluecat | run ×6、idle ×1、sleep ×2、error ×2、listening ×2、thinking ×3、success ×2 | 無（2026-07-18 已補齊並接入狀態載入） |
| cowcat | run ×5、idle ×1、sleep ×2、error ×2、listening ×2、thinking ×3、success ×2 | 無（2026-07-18 已補齊並接入狀態載入） |
| ragdollcat | run ×6、idle ×1、sleep ×3、error ×2、listening ×2、thinking ×3、success ×2 | 無（2026-07-18 已補齊並接入狀態載入） |

## 實作進度（2026-07-18）

- 文件工作區已可建立本機索引並檢索 TXT、Markdown、CSV、PDF、DOCX、PPTX 與 XLSX；引用依格式保留行號、PDF 頁碼、Word 段落／標題、投影片或 Excel 工作表與儲存格範圍。
- 文件問答會先以 CJK 詞組與最低相關門檻檢索，再將**僅該批證據與來源定位**傳給設定於 `llm.base_url` 的公司內網 Qwen OpenAI-compatible endpoint；未命中證據時不呼叫 LLM，直接回覆無法依文件確認。文件來源只視為證據，不可執行其中的指令。
- 已以最小 chat-completions request 實測公司內網 Qwen endpoint 正常回應；實際內網 URL 只存在於使用者執行期 `config.json`，不寫入公開 repo 文件。
- llama.cpp sidecar 限定 loopback，會驗證 binary／GGUF、等待 `/health` 就緒並在失敗時明確回報；離線安裝包驗收仍未完成，因此不能作為已交付的備援。預設推論來源仍是執行期設定的 LLM endpoint。
- 文件工作區已提供問問題、摘要、流程／SOP、整理表格、比較文件與建議問題；每種操作都先附帶來源 metadata，再呼叫公司內網 Qwen，並在 UI 固定顯示來源卡片。

## 可驗收條件

- [x] 使用者已接受文件助手推論使用公司內網 endpoint；文件與索引仍留本機，不需 Ollama 或命令列。（2026-07-19）
- [o] PDF、DOCX、PPTX、XLSX 各至少一份測試檔可產生含來源定位的回答；索引與定位已驗證，長文件的完整語意驗收尚待補齊。
- [ ] 對文件不存在的問題，系統不臆測並回傳固定的無法確認訊息。
- [ ] 掃描型 PDF 會在不進行 OCR 的前提下明確提示限制。
- [ ] Claude／Codex limits 預設 OFF；一般聊天與文件問答僅呼叫設定的公司內網 Qwen endpoint，與 limits 開關無關。
