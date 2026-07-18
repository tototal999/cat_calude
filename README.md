# ClaudeCat v2

> 規劃中的 v6.1 會將產品定位擴充為「桌面寵物 + 本機文件助手」：文件與量化模型均留在本機；Claude／Codex limits 為獨立可選監控。完整 MVP 規格見 [local-document-assistant-mvp.md](local-document-assistant-mvp.md)。

桌面藍貓寵物與公司內網 Qwen 文件助手。一般聊天與文件問答只使用設定於 `llm.base_url` 的公司內網 Qwen endpoint，不依賴 Claude 或 Codex。Claude／Codex limits 是獨立可選監控，預設 OFF。
v2 導入 Open WebUI 風格的聊天介面、歷史對話持久化（Sessions）、前後端分離架構，以及可攜式的 Windows EXE 打包修復。

## 需求
- Windows 10/11、Python 3.10+（含 tkinter，官方安裝包預設就有）
- `pip install requests Pillow pandas openpyxl python-pptx pywebview` (`pandas`, `openpyxl`, `python-pptx` 為交談與轉檔功能所需)
- 公司內網 Qwen endpoint 設定於 `%LOCALAPPDATA%\ClaudeCat\config.json`；聊天與文件功能不需要 Claude Code、Codex、Ollama 或其登入憑證。

## 執行
```bash
python cat.py
```
- 左鍵拖曳移動（貓或 % 徽章皆可）
- 單擊貓：開啟貼在貓旁的「問我一句」泡泡，Enter 後直接取得公司內網 Qwen 回答，不開完整聊天視窗。
- 右鍵選單：包含「交談...」、「排程...」等功能，可開啟現代化 WebView 聊天介面。
- 貓以本機互動、排程與閒置狀態呈現動畫；Claude／Codex limits 都是可選功能，首次啟用須由每位使用者在自己的電腦同意。未安裝或未登入兩者時，徽章顯示 `No use`，不會查詢。Codex 透過本機 app-server 讀取用量，屬非官方相容方式，可能隨 Codex 更新失效。

## 🌟 最新功能 (v6.0)

### 1. 現代化 Web 聊天介面 (Chatbot-UI Style)
透過點擊右鍵「交談...」，將開啟一個極具現代感的雙欄式聊天視窗：
- **深色主題 (Dark Mode)**：比照業界標準，採用 `#343541` 專業深色介面。
- **對話持久化 (Sessions)**：左側邊欄會自動列出過去的對話歷史，關閉視窗不再遺失對話。所有對話均以 JSON 格式安全地儲存在 `%LOCALAPPDATA%\ClaudeCat\sessions\` 中。
- **Markdown 與語法高亮**：內建 `highlight.js`，所有程式碼區塊不僅具備美觀的高亮，右上角皆附有獨立的「📋 Copy Code」按鈕。
- **快捷指令 (Slash Commands)**：在輸入框輸入 `/` 即可呼叫快速提示詞選單。
- **PPTX 一鍵轉檔**：對話若產生簡報大綱，可透過底部的「📽️ 匯出成 PPT」一鍵轉為 PowerPoint 簡報。

### 2. 前後端分離架構 (MVC Refactoring)
我們將原本龐大且混雜的 `chat.html` 與 Python 邏輯進行了深度解耦，為未來功能擴充打下堅實基礎：
- **Frontend**：完全由 `frontend/index.html`, `frontend/chat.js`, `frontend/style.css` 構成，乾淨純粹的 Web 技術棧。
- **Backend**：`backend/window_main.py` 專司 Pywebview 橋接；`backend/routes/api.py` 專司 JsApi 邏輯；`backend/services/llm_service.py` 負責 AI 串接。
- **Config & Prompts**：系統人設（System Prompt）已抽離至 `backend/prompts/system.txt`，可輕易替換。

## 疑難排解：徽章顯示 `!`

代表這輪輪詢抓用量失敗。**右鍵點貓 → 選單最上面那行（灰色不可點）** 會顯示確切原因。
完整歷史記錄看 log：**右鍵 → Show log**。檔案在 `%LOCALAPPDATA%\ClaudeCat\claudecat.log`。

## 架構
```
claude-cat/
├── backend/
│   ├── models/            # 資料結構與驗證
│   ├── prompts/           # system.txt (貓咪人設)
│   ├── routes/            # api.py (JsApi 橋接)
│   ├── services/          # llm_service.py, scheduler.py (核心業務)
│   └── window_main.py     # Pywebview 視窗管理
├── config/
│   └── settings.py        # 全域設定與 Config 讀取
├── frontend/
│   ├── chat.js            # 聊天介面邏輯 (包含 Slash commands, Sessions)
│   ├── index.html         # 雙欄式 Chatbot-UI 佈局
│   └── style.css          # 深色主題與動畫樣式
├── cat.py                 # 🐾 主程式：桌面寵物入口
├── worker.py              # 資料解析與 PPTX 背景工作程序 (避免卡死主線程)
├── api.py                 # usage-monitor-for-claude (MIT)
├── spritecat.py           # 精靈圖載入：去白背景、縮放、皮膚切換
├── winalpha.py            # UpdateLayeredWindow 逐像素 alpha 渲染
└── skins/                 # 皮膚資料夾 (支援動態抽換)
```

## 打包成 EXE
本專案採用 `onedir` 模式；Excel 解析改用 `openpyxl`／`xlrd`，不帶入 `pandas`／`numpy` 等未使用的大型依賴：
```bash
pip install pyinstaller
pyinstaller ClaudeCat.spec --clean -y
```
產出在 `dist\ClaudeCat`。`skins\` 與 `frontend\` 會一併凍入資料夾中。之後新增皮膚不需重新打包，丟到 exe 旁邊的 `skins\` 資料夾即可。2026-07-18 參考建置約 **73.5 MiB**；已以打包 EXE 驗證 PDF、DOCX、PPTX、XLSX 可完成文件索引。

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
