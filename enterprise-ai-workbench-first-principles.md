# ClaudeCat v7：企業 AI 工作台第一性原理分析

> 狀態：開發中；M1 核心與首條文件會議包已完成打包 EXE 自動驗收，待使用者人工 UI 驗收
> 更新日期：2026-07-19
> 目的：從企業使用者的真實問題與限制重新推導產品，不先假設一定需要 AI OS、Dashboard、Workflow 或 Plugin。

## 1. 問題不是「缺少聊天 AI」

企業使用者真正面對的是：

1. 多數同事無法直接使用外網 LLM。
2. 使用者不想理解模型、Provider、Token、OCR、MarkItDown 或 Prompt。
3. 工作輸入不是純聊天，而是 PDF、Word、Excel、SQL、Log、錯誤訊息與圖片。
4. 使用者需要的是可採用的工作成果，例如摘要、會議重點、審查報告或 Markdown，而不是一段看似合理的回答。
5. 公司需要資料邊界、來源證據、錯誤紀錄與可追溯性。
6. LLM 是機率系統，可能逾時、答錯、漏掉內容或修改不該修改的識別字。

因此產品問題應定義為：

> 如何讓無法使用外網 AI 的企業使用者，用最低操作成本，將工作資料安全地轉換成可驗證、可交付的成果？

## 2. 不可再分解的基本事實

### 事實 A：模型不是產品

模型只是工作鏈中的一個處理器。使用者不應為每個任務選模型、組 Prompt 或決定重試方式。

推導：

- AI Router 是底層能力，不是主要畫面。
- 一般使用者只選工作目的，不選模型名稱。
- 每次路由仍須記錄實際 Provider／模型，供診斷與稽核。

### 事實 B：輸入格式不可消失，但可以被統一

PDF、Excel、SQL 與 Log 的解析方法不同，不能真的「不管格式」。系統必須在背後確定性辨識格式，再交給正確處理器。

推導：

- Workspace 是統一入口，不是單一萬用解析器。
- 類型判斷優先使用副檔名、MIME、JSON parser 與 SQL／Log 規則。
- 無法可靠判斷時請使用者確認，不讓 LLM 猜格式。

### 事實 C：企業價值來自成果，不是對話長度

如果使用者仍要自己複製摘要、再次要求翻譯、再建立 Markdown，產品只是把多個聊天步驟排在一起。

推導：

- Workflow 的輸出必須是具名 Artifact，例如 `meeting-notes.md`。
- 每個步驟應有輸入、輸出、狀態與錯誤。
- 已完成步驟的成果在後續失敗時仍可查看。

### 事實 D：確定性與機率性工作必須分開

JSON 驗證、SQL 格式化、檔案類型判斷、狀態轉移與重試次數，都不應交由 LLM 決定。

推導：

```text
確定性程式
├─ 辨識格式
├─ 解析／驗證
├─ 遮罩與還原
├─ Workflow 狀態
├─ 重試／逾時
└─ 寫出 Artifact

LLM
├─ 摘要
├─ 語意分類
├─ 解釋
├─ 比較
└─ 建議
```

### 事實 E：企業環境預設不信任外部執行碼

「下載 Plugin 後直接執行」會引入任意程式碼、供應鏈、版本、權限與回滾問題。

推導：

- 第一版 Plugin 只能是內建 Manifest 與白名單 Step Handler。
- 不支援下載任意 Python／JavaScript。
- Marketplace、簽章、更新與回滾是未來能力，不是 MVP。

### 事實 F：桌面寵物不是核心運算層

桌寵的價值是常駐、低打擾、容易啟動與顯示工作狀態。

推導：

- 桌寵定位為 Workflow Launcher 與狀態提示器。
- 複雜工作仍在 Workspace 顯示輸入、進度、來源與輸出。
- 不把完整 Dashboard 塞在貓旁的小視窗。

## 3. 從基本事實推導出的產品

最準確的近期定位是：

> **Local-first Enterprise AI Workbench：讓 AI 從回答問題，變成安全地完成一段可驗證工作。**

產品由三個使用者層組成：

| 層級 | 職責 | 比重 |
|---|---|---:|
| Launcher | 桌寵、右鍵選單、系統匣、工作狀態通知 | 10% |
| Workspace | 統一拖放／貼上、類型確認、Workflow 建議、結果檢視 | 30% |
| Workflow | 執行步驟、路由、來源、錯誤、輸出、重跑 | 60% |

Dashboard 不是獨立核心產品；它只應顯示與工作決策有關的狀態。

## 4. 現有 ClaudeCat 能保留什麼

| 現有能力 | 在 v7 的角色 |
|---|---|
| 桌寵、系統匣、右鍵選單 | Workflow Launcher |
| pywebview 單例視窗 | Workspace UI 容器 |
| `document_service.py` | 文件解析、索引、檢索 Step |
| `json_tools.py` | 確定性 JSON Step |
| `translation_service.py` | 翻譯 Step |
| `llm_service.model_for_task()` | AI Router 的起點 |
| `worker.py` | 重依賴與檔案處理的隔離程序 |
| Sessions／Markdown 匯出 | Run History／Artifact 的參考實作 |

不需要更換 Python、Tkinter、pywebview，也不需要導入 Electron。

## 5. 真正缺少的最小核心

### 5.1 Workflow Definition

描述工作名稱、輸入類型、步驟與輸出，不包含任意可執行程式碼。

```json
{
  "id": "document-meeting-pack",
  "version": 1,
  "input_types": ["pdf", "docx"],
  "steps": [
    "parse_document",
    "summarize",
    "meeting_notes",
    "export_markdown"
  ]
}
```

### 5.2 Workflow Run

最小狀態：

```text
pending → running → completed
                  ↘ failed
                  ↘ cancelled
```

每次執行至少保存：

- `run_id`
- Workflow id／version
- 輸入檔名與本機來源
- 目前 Step
- 每一步狀態、時間與安全錯誤
- 實際使用的 Provider／模型
- 產生的 Artifact 路徑

### 5.3 Allowlisted Step Handler

第一版只允許內建處理器：

- `parse_document`
- `retrieve_evidence`
- `json_validate`
- `translate`
- `llm_task`
- `export_markdown`

### 5.4 Artifact

Workflow 必須產生可交付成果，不只回傳聊天文字。

第一版只需要：

- Markdown
- JSON
- 現有文件來源引用

## 6. 最小垂直切片

第一條 Workflow 應選擇能最大量重用現有程式、又能證明產品價值的流程：

```text
文件會議包

拖入 PDF／DOCX
  → 本機解析與索引
  → 依來源摘要
  → 產生會議重點
  → 可選翻譯
  → 匯出 Markdown
```

選它而不是先做 SQL／Log／OCR，原因：

1. 現有文件解析、來源定位、LLM 路由、翻譯與 Markdown 匯出大多可重用。
2. 能一次驗證 Workspace、Workflow、Router、Artifact 與來源證據。
3. 不需要新增 OCR、資料庫連線或大型依賴。

### 垂直切片驗收

1. 使用者拖入一份可讀文件後，三次操作內取得 Markdown。
2. UI 顯示目前步驟與成功／失敗狀態。
3. 摘要與會議重點保留來源。
4. 長文件明示抽樣涵蓋率。
5. 翻譯失敗不會刪除已完成摘要。
6. 匯出失敗不會把 Workflow 標成完成。
7. 關閉視窗後可查看最後一次 Run 與 Artifact。
8. 文件內容不會因 Workflow 功能自動傳到外網。

## 7. AI Router 的正確邊界

現階段 Router 預設只允許：

```text
Company LLM
Local llama.cpp
```

Claude／Codex 仍只作可選 limits 顯示，不參與聊天或 Workflow。這符合目前「多數同事不能上外網」與既有產品決策。

若未來要加入外部 Provider，必須先有：

- 公司核准的資料分類政策
- 每位使用者明確同意
- 哪些 Workflow／欄位可外送的白名單
- 路由與外送稽核紀錄
- 禁止 fallback 時的明確停止行為

Router 不得因公司模型失敗就默默把文件送到外部。

## 8. 分階段路線

### M0：凍結產品邊界

- 確認產品名稱為企業 AI 工作台；AI OS 僅作長期願景。
- 確認外部 Provider 預設禁止。
- 確認首條 Workflow 為文件會議包。

### M1：Workflow 核心

- Workflow Definition／Run／StepResult／Artifact。
- 白名單 Step Handler。
- atomic JSON 執行紀錄。
- 明確失敗、取消與有限重試。

### M2：文件會議包

- 串接現有文件、LLM、翻譯與匯出能力。
- UI 顯示進度、來源與 Artifact。
- 完成打包 EXE 端對端驗收。

### M3：統一 Workspace

- 拖放與貼上入口。
- 確定性格式辨識。
- 建議 Workflow，使用者確認後才執行。
- 最近 Run 與 Artifact。

### M4：第二批 Workflow

- Log Triage：本機擷取 Error → LLM Root Cause → Markdown。
- SQL Review：本機 Format／規則檢查 → LLM Explain／Review → Markdown。
- SQL 第一版只分析，不連資料庫、不執行 SQL。

### M5：Plugin Catalog

- 內建 Manifest、版本、輸入類型、權限與步驟。
- 不支援任意下載執行碼。

### M6：工作導向 Dashboard

- Provider 在線狀態。
- 目前 Workflow／步驟。
- 最近成功／失敗 Run。
- 最近 Artifact。
- Claude／Codex limits 維持選用。

CPU／GPU 資訊等到本機模型成為主要運算來源後再評估。

## 9. 第一版明確不做

- 任意下載並執行第三方 Plugin
- 自動呼叫 Claude／Codex
- 多 Agent 自主協作
- Workflow 視覺化編輯器
- OCR／圖片理解
- URL 自動抓取
- API Spec 轉 Postman
- GPU 儀表板
- 雲端同步與多人知識庫

## 10. 主要風險與控制方式

| 風險 | 控制方式 |
|---|---|
| 「AI OS」範圍無限擴大 | 先完成一條文件會議包垂直切片 |
| LLM 回答看似正確但實際錯誤 | 保留來源、coverage 與確定性驗證 |
| Workflow 失敗卻顯示完成 | 使用明確狀態機與 StepResult |
| Plugin 造成任意程式碼執行 | 只允許 Manifest＋白名單 Handler |
| 公司模型失敗時資料被外送 | Router 預設禁止外部 fallback |
| 執行紀錄與文件洩漏 | 存本機、log 不記全文、匯出由使用者觸發 |
| 架構先行造成過度設計 | 第一版一次只跑一個 Workflow，使用 atomic JSON，不導入資料庫與佇列 |

## 11. 何時才可以稱為 AI OS

至少同時達成以下條件：

1. 有三條以上經人工驗收、可重跑的 Workflow。
2. Workspace 能穩定辨識輸入並推薦工作。
3. Workflow 有狀態、取消、失敗、Artifact 與歷史。
4. Router 有可稽核政策，而不只是模型下拉選單。
5. Plugin 有版本、權限與安全邊界。
6. 使用者不需要理解背後模型與工具仍能完成工作。

在此之前，對外稱「企業 AI 工作台」比「AI OS」更準確，也較不會過度承諾。
