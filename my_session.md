# Session 摘要
**儲存時間**：2026-07-24 15:10
**工作目錄**：C:\Users\TF000054\claude\claude-cat

## 工作目標
延續 ClaudeCat v7 開發：新增 wuma（猴子）skin、整理使用者 SOP 簡報命名與內容、修正 Codex 用量誤觸發貓咪睡眠動畫的問題，並依序重建 7.0.5、7.0.6 發布版。

## 已完成事項
- **檔案改名**：`使用者SOP_投影版.pptx/.pdf/大綱.md` 全面改名為 `桌寵與LLM.*`；`skins/使用者SOP` 資料夾改名為 `skins/桌寵與LLM`（原始討論；`skins/wuma` 維持原名不改，因為要跟 bluecat/cowcat/ragdollcat 命名風格一致）。`tools/sop-deck-gen.js` 與 `tools/build-release.ps1` 內硬寫的舊檔名（含 char-code 編碼的 unicode 字串）同步更新。
- **新增 wuma skin**：把 `skins/wuma/spritesheet.webp`（8×11 網格圖，每格 192×208px）切成獨立 PNG。最終版本是 **16 張 run + 8 張 sleep + 1 張 idle**（不是最初隨手切的 74 張全部塞進 run——那版已被取代/整理過）。已用 `spritecat.load_state_frames` 確認正確載入。
- **Agenda 頁順序與內容修正**：`tools/sop-deck-gen.js` 裡 Agenda 投影片原本排在第 5 張（封面、能做什麼×2、切換模型之後），且列的項目跟實際投影片順序、涵蓋範圍都對不上。已搬到封面後的第 2 張，並重寫內容涵蓋全部主題（能做什麼／模型、快速提問與長回答、LLM 介面、文件相關、工具箱與 Skin、桌寵管理），依 `feature-policy.json` 動態增減字樣。`桌寵與LLM大綱.md` 同步調整章節編號。
- **PDF 未重新產生**：本機沒裝 LibreOffice/soffice，無法自動轉 PDF；使用者指示先刪除舊版 `桌寵與LLM.pdf`（頁序對不上），之後手動用 PowerPoint 匯出。
- **Codex 不再影響貓咪動作**（本次最重要的邏輯修正）：`cat.py` 的 `_effective_usage()`、`_effective_error()`、`_monitor_active()` 原本會把 Codex 用量／錯誤跟 Claude 一起算進「有效用量」，導致 Codex 用量到 100% 時貓咪會凍結入睡（`_should_sleep()`）。使用者要求「Cat 的動作只綁定 Claude，不參考 Codex」，已移除三個函式裡的 Codex 分支；徽章（badge）顯示仍保留 Claude／Codex 兩行資訊，只有「動作」邏輯改成純 Claude。100 個測試全過，額外手動驗證：Claude 關閉、Codex 100% 時 `_effective_usage()` 回傳 `None`、`_monitor_active()` 回傳 `False`、`_should_sleep()` 回傳 `False`。
- **EXE 建置**：7.0.4 → **7.0.5**（wuma skin + Agenda 順序修正）→ **7.0.6**（Codex 解耦 + Agenda 內容修正）。兩次都 8 步驗證全過。
- **建置環境筆記**：`node tools/sop-deck-gen.js` 需要 `NODE_PATH="C:\Users\TF000054\AppData\Roaming\npm\node_modules"`（pptxgenjs 只裝在全域 npm，專案內沒有 `node_modules`/`package.json`）。

## 重要決定
- **skins/wuma 資料夾維持原名**：使用者確認過，不改成「桌寵」這種通稱，保留跟其他 skin 一致的具體命名風格。
- **Codex 用量徹底跟貓咪動作解耦**：徽章顯示可以繼續秀 Codex 資訊，但速度、睡姿、錯誤姿勢一律只看 Claude；這是使用者明確反饋的行為準則，日後任何動畫相關邏輯都不該再摸 Codex 的用量／錯誤狀態。
- **Agenda 頁不必跟大綱 1:1**：`.md` 大綱本身就聲明「不等於實際發布簡報」，Agenda 摘要可以把多張投影片合併成一行（例如「工具箱與 Skin：JSON、翻譯、切換 Skin、用量顯示」），但順序跟涵蓋範圍必須對得上實際投影片。

## 待辦事項
- [ ] 上 Git：commit 這次的全部改動並 push（進行中，本則訊息之後動作）
- [ ] 使用者實機驗證 7.0.6：Agenda 頁序/內容、wuma skin 動畫、Codex 100% 時貓咪不再睡覺
- [ ] `桌寵與LLM.pdf` 待手動用 PowerPoint 從新版 pptx 匯出
- [ ] 開 PR：feat/multi-endpoint-llm-and-ui-fixes（上次 session 已產生連結但尚未開）
- [ ] gemma 格式測試（是否需指定 `# 標題` 格式才能產簡報）——延續自上次 session，本次未處理

## 關鍵程式碼

```python
# cat.py：Codex 不再影響動作，只影響徽章顯示
def _effective_usage(self) -> float | None:
    ds = self.debug_state.get()
    if ds == 'error':
        return None
    if ds == 'full':
        return 100.0
    if self.monitor_enabled.get() and self.usage_pct is not None:
        return self.usage_pct
    return None
```

```python
# 切割 wuma spritesheet.webp 用的邏輯（8x11 網格，192x208/格）
cols, rows = 8, 11
cw, ch = W // cols, H // rows
# 非透明格才輸出成獨立 PNG；後續再依姿勢分類成 run/sleep/idle
```

## 重要檔案
- `cat.py` — `_effective_usage`/`_effective_error`/`_monitor_active` 移除 Codex 分支
- `skins/wuma/` — 新 skin：16 run + 8 sleep + 1 idle PNG（+ 原始 `pet.json`、`spritesheet.webp` 保留備查）
- `tools/sop-deck-gen.js` — Agenda 搬到第 2 張、內容重寫、舊檔名更新
- `桌寵與LLM.pptx` / `桌寵與LLM大綱.md` — 已改名並更新內容（`.pdf` 已刪除待補）
- `tools/build-release.ps1` — 舊檔名 char-code 更新為新檔名
- `dist\ClaudeCat\ClaudeCat.exe` — 目前版本 7.0.6

## 其他備註
- 建置指令：`powershell -NoProfile -ExecutionPolicy Bypass -File tools\build-release.ps1 -Version X.X.X`
- 測試指令：`%LOCALAPPDATA%\Programs\Python\Python311\python.exe -m unittest test_logic -v`
- 簡報產生器需要先設 `NODE_PATH` 指到全域 npm 套件目錄才能跑 `node tools/sop-deck-gen.js`
