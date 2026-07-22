# ClaudeCat 桌面 AI 工具箱 MVP

> 版本：v6.2（2026-07-19）
> 對象：只能使用公司內網或本機模型的 Windows 同事。

## 目標與邊界

在既有 ClaudeCat 聊天／文件助手旁，提供可在單一 pywebview 視窗中使用的 JSON、翻譯與模型設定工具。

- 可由確定性程式完成的操作，不呼叫 LLM。
- 語意理解、翻譯與文件回答才使用目前設定的 OpenAI-compatible 公司／本機 LLM。
- 「無外網」不代表不需要連線：公司 LLM 模式需要連公司內網；本機 llama.cpp 可作為離線替代。
- 不在公開程式碼、文件或預設設定中放入內網 URL、模型名稱、API Key 或文件內容。
- API Key 不由 MVP 設定畫面編輯；安裝包或使用者執行期 `config.json` 負責提供，避免未具憑證庫卻宣稱已加密保存。

## 第一版功能

### JSON 工具（不使用 LLM）

- 貼上 JSON 後執行 Format、Minify、Validate、Copy、文字搜尋。
- Validate 回傳 JSON decoder 的行、欄與訊息；不修改原輸入。
- Tree View 由前端把已驗證的 JSON 結構渲染成可展開節點，並顯示 JSONPath。
- Tree 的展開／收合與型別色彩互動參考 [pgrabovets/json-view](https://github.com/pgrabovets/json-view) 的產品概念；MVP 保留內建實作，不捆綁 npm 套件或 CDN，確保離線可用。
- 預設不排序 Object key，也不自動覆寫使用者原文。

### 翻譯

- 來源語言為自動偵測；目標先支援繁中、英文。
- 來源支援自動偵測、英文、繁體中文、簡體中文；目標支援英文、繁體中文、簡體中文，
  並提供雙箭頭交換來源與目標。
- 模式：一般、技術、商務、中英對照。
- 可選擇保留程式碼／表格、套用本機術語表。
- 提示明定不得改動程式碼、SQL 欄位、單引號常數、JSON Key、API path、檔名與錯誤碼。
- 預設術語表為小型本機字典，可由執行期設定檔覆寫或擴充。

### 模型選擇與路由

- 一般聊天頂端顯示建置時核准的公司模型清單；有多個模型時允許使用者手動切換並保存。
- 公司版不開放 Provider、API URL 或 API Key 編輯；任務模型也只能從公司白名單選取。
- 翻譯、文件、程式分析與錯誤分析優先走 `task_models`；一般聊天使用頂端選定模型。
- 模型健康檢查透過現有 OpenAI-compatible `/chat/completions` 發送極小請求，回傳成功或明確錯誤。

## 執行期設定範例

以下為設定結構示意。公司端點與核准模型由受 Git 忽略的建置輸入提供並編譯進 EXE；
執行期 `%LOCALAPPDATA%\ClaudeCat\config.json` 不得提交，且打包版會覆寫其中的外部端點或非核准模型：

```json
{
  "llm": {
    "provider": "company",
    "base_url": "http://internal-host/v1",
    "model": "company-default",
    "request_timeout": 120,
    "model_mode": "auto",
    "model_modes": {
      "fast": "company-small",
      "quality": "company-large",
      "code": "company-coder",
      "translation": "company-translate"
    },
    "task_models": {
      "translation": "company-translate",
      "document": "company-large",
      "code": "company-coder"
    },
    "translation_glossary": {
      "Purchase Order": "採購單",
      "Receipt": "收料",
      "Reject": "剔退",
      "Organization": "庫存組織",
      "Concurrent Program": "並行程式"
    }
  }
}
```

## 驗收

1. 不啟動 LLM 時，JSON Format／Minify／Validate／Tree View 均可使用。
2. 不合法 JSON 顯示正確行、欄與訊息，且不改輸入。
3. 翻譯依 task router 選取翻譯模型；失敗會直接顯示端點錯誤。
4. 技術翻譯提示包含保護程式碼、SQL、JSON Key、API path 與錯誤碼的規則。
5. 未設定任務模型時可安全退回目前模式或預設模型。
6. 模型健康檢查回報在線或具體失敗原因；不記錄 API Key。

## 實作狀態（2026-07-19）

- 程式與自動驗證完成：Python 3.11 `test_logic.py` 全數通過、`node --check frontend/chat.js` 與 `git diff --check` 通過（測試數量見 [in_progress.md](in_progress.md)）。
- 待內網實測：使用者設定公司端點後，執行 Health Check 與翻譯請求，確認實際回應與失敗訊息。
- 發布驗證完成：已於 2026-07-19 重新打包新版 EXE，啟動 5 秒仍存活；打包後文件驗證器亦通過 PDF／DOCX／PPTX／XLSX 索引與來源定位測試。

## 後續（不列入 MVP）

- 背景剪貼簿偵測與桌面氣泡建議。
- JSON ↔ YAML／CSV／XML、Object Key 排序與差異比較。
- 翻譯歷史、釘選結果與完整敏感資料遮罩策略。
- Windows Credential Manager／DPAPI 整合後，才允許 UI 管理 API Key。
