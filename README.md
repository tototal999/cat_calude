# ClaudeCat

> v6.1 已將產品定位擴充為「桌面寵物 + 本機文件助手」：文件與索引均留在本機；Claude／Codex limits 為獨立可選監控。完整 MVP 規格見 [local-document-assistant-mvp.md](local-document-assistant-mvp.md)。
> v6.2 再擴充為「桌面 AI 工具箱」，加入 JSON 工具與翻譯分頁，規格見 [desktop-ai-toolbox-mvp.md](desktop-ai-toolbox-mvp.md)。
> v7 將桌寵定位為 Workflow Launcher，逐步演進為 Local-first「企業 AI 工作台」；第一性原理分析見 [enterprise-ai-workbench-first-principles.md](enterprise-ai-workbench-first-principles.md)。首條「文件會議包」Workflow 已進入開發驗證。

桌面藍貓寵物與公司內網 Qwen 文件助手。一般聊天與文件問答只使用設定於 `llm.base_url` 的公司內網 Qwen endpoint，不依賴 Claude 或 Codex。Claude／Codex limits 是獨立可選監控，預設 OFF。
專案導入 Open WebUI 風格的聊天介面、歷史對話持久化（Sessions）、前後端分離架構，以及可攜式的 Windows EXE 打包修復。

## 需求
- Windows 10/11、Python 3.10+（含 tkinter，官方安裝包預設就有）
- 必要套件：

  ```bash
  pip install requests Pillow pywebview pystray openpyxl xlrd python-pptx python-docx pypdf
  ```

  | 套件 | 用途 |
  |---|---|
  | `requests` | 用量 API 與 LLM 呼叫 |
  | `Pillow` | 精靈圖縮放、系統匣圖示 |
  | `pywebview` | 交談／文件／工具視窗 |
  | `pystray` | Windows 系統匣 |
  | `openpyxl`／`xlrd` | XLSX／舊版 XLS 解析 |
  | `python-pptx` | PPTX 解析與匯出 |
  | `python-docx` | DOCX 解析 |
  | `pypdf` | PDF 解析與頁碼定位 |

  選用：`markitdown`（文件轉 Markdown，未安裝時退回原生解析）。
  **不需要 `pandas`／`numpy`**——v6.1 起 Excel 已改用 `openpyxl`／`xlrd`，打包體積因此縮減。
- 公司內網 Qwen endpoint 設定於 `%LOCALAPPDATA%\ClaudeCat\config.json`；聊天與文件功能不需要 Claude Code、Codex、Ollama 或其登入憑證。

## 執行
```bash
python cat.py
```
- 左鍵拖曳移動（貓或 % 徽章皆可）
- 單擊貓：開啟貼在貓旁的「問我一句」泡泡，Enter 後直接取得公司內網 Qwen 回答，不開完整聊天視窗。
- 右鍵選單：直接提供「快速提問」、「交談（LLM 介面）」、「文件助手」、「JSON 工具」、「翻譯」、「模型設定」與「排程」；也可切換 Skin 與調整桌寵設定。
- Windows 系統匣：可顯示／隱藏桌寵、快速提問、開啟文件助手或結束程式。
- 貓以本機互動、排程與閒置狀態呈現動畫；Claude／Codex limits 都是可選功能，首次啟用須由每位使用者在自己的電腦同意。未安裝或未登入兩者時，徽章顯示 `No use`，不會查詢；同時顯示兩者時，徽章以 Claude／Codex 上下兩行呈現。Codex 透過本機 app-server 讀取用量，屬非官方相容方式，可能隨 Codex 更新失效。

## 🌟 最新功能 (v6.2 桌面 AI 工具箱)

### v7 開發中：文件會議包

文件助手選取 PDF／DOCX 後可建立「文件會議包」：
本機檢索來源、透過文件任務模型產生摘要與會議重點、可選英文翻譯，最後輸出 Markdown。
UI 會顯示每一步狀態、coverage、來源定位與 Artifact 路徑；後續步驟失敗時，
已完成摘要仍保留為部分成果，並可按「重新執行」（每條重試鏈最多 3 次）。
同一失敗 Run 只能建立一筆重試；已結束歷史自動保留最近 50 筆，文件頁也可手動清理
已結束 Run 與 Markdown 成果，執行中的工作不會被刪除。
程式異常結束後，前一個程序留下的 pending／running Run 會在下次讀取時標記為可重試失敗；
損毀 Run 的 Markdown 成果在診斷保留期內不會被孤兒清理誤刪。
Workflow 只使用公司 LLM 或已啟用的本機 llama.cpp，不會呼叫 Claude／Codex。

### 1. JSON 工具分頁

Format、Minify、Validate、搜尋、Copy、Tree View 與 JSONPath。
**全部由本機確定性程式處理，完全不呼叫 LLM**，所以 endpoint 離線時照樣可用。
非法 JSON 會直接指出錯誤的行與欄；輸入大小、巢狀深度與節點數皆有上限保護。

### 2. 英／繁中翻譯分頁

支援一般、技術、商務、中英對照四種語氣。
程式碼、SQL、JSON Key、API path、檔名與錯誤碼會先以佔位符鎖定再送出，
還原時逐一比對；模型若未完整保留這些內容，會直接回報錯誤而非默默吐出壞結果。
術語表存在本機。

### 3. 模型模式與任務路由

- 頂端模型選單改為一般使用者可理解的**模式**：自動、快速、高品質、程式分析、翻譯，
  不直接曝露模型 ID。端點、模型、Timeout 與模式對應只在「進階設定」頁修改。
- **任務模型路由**：翻譯、文件、程式分析、錯誤分析與一般聊天可各自指定模型；
  未設定時回退至模式對應，再退回預設模型。
- 進階設定頁提供 Health Check。目前只驗證聊天模型，其餘任務路由待逐一驗證。

> **API Key 不由 UI 管理。** 憑證僅由公司安裝程序或使用者的執行期 `config.json` 提供，
> 避免以未加密的 UI 欄位保存。詳見下方「LLM 交談設定」。

---

## v6.0 功能（沿用至今）

### 1. 現代化 Web 聊天介面 (Chatbot-UI Style)
透過點擊右鍵「交談（LLM 介面）...」，將開啟一個極具現代感的雙欄式聊天視窗：
- **深色主題 (Dark Mode)**：極深灰配色，底色 `#101112`、面板 `#171819`、強調色 `#4f8cff`（定義於 `frontend/style.css` 的 `:root`）。
- **對話持久化 (Sessions)**：左側邊欄會自動列出過去的對話歷史，關閉視窗不再遺失對話。所有對話均以 JSON 格式安全地儲存在 `%LOCALAPPDATA%\ClaudeCat\sessions\` 中。
- **Markdown 與程式碼複製**：離線版不載入語法高亮套件；所有程式碼區塊右上角仍有獨立的「📋 Copy Code」按鈕。
- **快捷指令 (Slash Commands)**：在輸入框輸入 `/` 即可呼叫快速提示詞選單。
- **PPTX 一鍵轉檔**：對話若產生簡報大綱，可透過底部的「📽️ 匯出成 PPT」一鍵轉為 PowerPoint 簡報。

### 2. 前後端分離架構 (MVC Refactoring)
我們將原本龐大且混雜的 `chat.html` 與 Python 邏輯進行了深度解耦，為未來功能擴充打下堅實基礎：
- **Frontend**：完全由 `frontend/index.html`, `frontend/chat.js`, `frontend/style.css` 構成，乾淨純粹的 Web 技術棧。
- **Backend**：`backend/window_main.py` 專司 Pywebview 橋接；`backend/routes/api.py` 專司 JsApi 邏輯；`backend/services/llm_service.py` 負責 AI 串接。
- **Config & Prompts**：系統人設（System Prompt）已抽離至 `backend/prompts/system.txt`，可輕易替換。

## 疑難排解：徽章顯示 `!`

代表這輪輪詢抓用量失敗。**右鍵點貓 → 選單最上面那行（灰色不可點）** 會顯示確切原因。
完整歷史記錄看 log：**右鍵 → 開啟記錄**。檔案在 `%LOCALAPPDATA%\ClaudeCat\claudecat.log`。

## 架構
```
claude-cat/
├── backend/
│   ├── prompts/
│   │   └── system.txt              # 貓咪人設 system prompt
│   ├── routes/
│   │   └── api.py                  # JsApi 橋接
│   ├── services/
│   │   ├── llm_service.py          # LLM 客戶端與任務模型路由
│   │   ├── document_service.py     # 文件索引、切塊、檢索與來源定位
│   │   ├── workflow_service.py     # 白名單 Workflow、執行狀態與 Artifact
│   │   ├── json_tools.py           # JSON 工具（本機確定性處理，不呼叫 LLM）
│   │   ├── translation_service.py  # 翻譯與佔位符保護／還原驗證
│   │   ├── tray_service.py         # Windows 系統匣
│   │   ├── local_llm.py            # llama-server sidecar 生命週期管理
│   │   └── codex_limits.py         # Codex 用量（非官方 app-server 讀取）
│   └── window_main.py              # Pywebview 視窗管理
├── config/
│   └── settings.py                 # 全域設定與 Config 讀取
├── frontend/
│   ├── chat.js                     # 前端邏輯 (Slash commands, Sessions, 工具分頁)
│   ├── index.html                  # 雙欄式 Chatbot-UI 佈局
│   └── style.css                   # 深色主題與動畫樣式
├── pet/
│   └── state_machine.py            # PetState 狀態機
├── plugins/
│   └── builtin.py                  # 內建 plugin（僅限固定白名單事件）
├── cat.py                          # 🐾 主程式：桌面寵物入口
├── scheduler.py                    # 排程引擎（daily / weekly / hourly）
├── worker.py                       # 資料解析與 PPTX 背景工作程序 (避免卡死主線程)
├── api.py                          # usage-monitor-for-claude (MIT)
├── spritecat.py                    # 精靈圖載入：去白背景、縮放、皮膚切換
├── winalpha.py                     # UpdateLayeredWindow 逐像素 alpha 渲染
├── vectorcat.py                    # 向量貓（已改用精靈圖，保留備援）
└── skins/                          # 皮膚資料夾 (支援動態抽換)
```

## 打包成 EXE
本專案採用 `onedir` 模式；Excel 解析改用 `openpyxl`／`xlrd`，不帶入 `pandas`／`numpy` 等未使用的大型依賴：
```bash
pip install pyinstaller pystray
pyinstaller ClaudeCat.spec --clean -y
```
產出在 `dist\ClaudeCat`。`skins\` 與 `frontend\` 會一併凍入資料夾中。之後新增皮膚不需重新打包，丟到 exe 旁邊的 `skins\` 資料夾即可。2026-07-19 最新建置約 **77.1 MiB**（含三套完整狀態素材）；已以打包 EXE 驗證 PDF、DOCX、PPTX、XLSX 文件索引，以及 DOCX → 來源檢索 → 本機假 LLM → Markdown Artifact 的完整文件會議包。

桌寵會顯示為 Windows 工作列的 `ClaudeCat` 項目；可直接按該項目的關閉按鈕結束程式，位置會照既有流程保存。

## LLM 交談設定
**這是公開 repo, 真實端點不寫進程式碼**——實際設定寫在執行期的 `%LOCALAPPDATA%\ClaudeCat\config.json`（不進版控）：
```json
{
  "llm": {
    "base_url": "http://your-host:8000/v1",
    "model": "your-model-name",
    "api_key": ""
  }
}
```

**API Key 不在 UI 編輯**：`api_key` 只能由公司安裝程序或使用者手動寫入這份執行期
`config.json`。程式不提供輸入憑證的 UI 欄位，避免以未加密形式保存。內網端點若不需要
驗證，留空字串即可。

### 離線本機模型（v6.1）

公司安裝包將 `llama-server.exe` 與 GGUF 模型放在 `%LOCALAPPDATA%\ClaudeCat\` 後，可於同一份 `config.json` 啟用。程式只會啟動 `127.0.0.1` 的服務，結束時一併停止；若檔案不存在，會明確顯示原因。一般聊天與文件問答預設使用 `llm.base_url` 設定的公司內網 Qwen endpoint；sidecar 是未來無內網時的備援。

```json
{
  "local_llm": {
    "enabled": true,
    "server": "llama-server.exe",
    "model": "company-model.gguf",
    "model_id": "company-local-model",
    "port": 8080
  }
}
```

## 安全性與效能

- 聊天訊息、對話標題與排程內容會先轉義再顯示，避免 HTML 被執行。
- 對話 session 僅接受 UUID，避免透過路徑名稱存取 sessions 目錄外的檔案。
- 開發環境的附件與 PPT 轉換會直接啟動 `worker.py`，不再載入完整的桌面程式。
- 附件預設限制為 10 MiB 與 50,000 個字元；可在 `%LOCALAPPDATA%\\ClaudeCat\\config.json` 的 `llm` 區塊設定：

```json
{
  "llm": {
    "max_file_bytes": 10485760,
    "max_file_chars": 50000
  }
}
```
