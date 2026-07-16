# ClaudeCat

桌面藍貓寵物，跑速反映 Claude 5 小時 session 用量。

## 需求
- Windows 10/11、Python 3.10+（含 tkinter，官方安裝包預設就有）
- `pip install requests Pillow`
- **Claude Code CLI 已登入**（讀取 `~/.claude/.credentials.json`）
  ⚠️ **只裝 Claude Desktop 不夠**——Claude Desktop 和 Claude Code CLI
  是兩個不同的登入系統，憑證不共用。這隻貓只認 Claude Code CLI 寫入的
  `.credentials.json`。安裝：`npm install -g @anthropic-ai/claude-code`
  → `claude login`（跟 Desktop 分開登入，帳號相同也要各登一次）

## 執行
```
python cat.py
```
- 左鍵拖曳移動（貓或 % 徽章皆可）
- 右鍵選單：百分比 / 手動刷新 / 置頂切換 / 顯示%開關 / Size（64-256px）/
  Refresh（輪詢間隔）/ Skin（切換皮膚）/ Face right（朝向切換）/
  Test（強制預覽錯誤與 100% 狀態）/ Show log / 結束
- 同一時間只允許一個實例：重複執行會直接靜默結束（寫入 log），
  不會出現第二隻貓
- 貓下方預設顯示用量徽章：`session% Wweekly% | 重置時間`
  （例如 `64% W70% | 17:00`；W 是七日週限額——session 重置了週限額不會重置，
  常常是先撞到的那道牆），錯誤時變紅色 `!`，可從右鍵選單關閉
- **session 或週限額任一超過 90%，徽章變紅色警示**
- 設定會記住（skin/大小/朝向/置頂/輪詢間隔/位置），存於
  `%LOCALAPPDATA%\ClaudeCat\config.json`；位置在右鍵 Quit 正常結束時儲存
- 用量 0-25% 散步 → 25-50% 小跑 → 50-75% 快跑 → 75-95% 狂奔 →
  >95% 靜止（`_09` 待命姿勢）；API 無法連線時以預設速度播放動畫
- 若該皮膚有睡覺圖片（檔名含 `sleep`）：Claude 沒在執行（抓不到用量）
  或 session 用滿 100% 時，貓會改顯示睡覺姿勢（多張則慢速循環）

## 疑難排解：徽章顯示 `!`

代表這輪輪詢抓用量失敗。**右鍵點貓 → 選單最上面那行（灰色不可點）**
會顯示確切原因：

| 訊息 | 原因 | 解法 |
|---|---|---|
| `No OAuth token found (log in to Claude Code)` | 沒登入 Claude Code CLI（只裝 Desktop 也會這樣） | 裝 CLI 並 `claude login` |
| `Connection error` | 網路/防火牆/Proxy 擋住 `api.anthropic.com` | 檢查網路連線 |
| `Auth token expired` | token 過期，程式會自動背景跑 `claude update` 嘗試刷新 | 需要 `claude` CLI 在 PATH 上 |
| `HTTP error 429` | 輪詢太頻繁被限流 | 等待，或把 Refresh 間隔調大 |
| `Quota field "five_hour" missing in API response` | Anthropic 端 API 欄位改名 | 回報，需改 `cat.py` 的 `QUOTA_FIELD` 常數 |

完整歷史記錄看 log：**右鍵 → Show log** 直接跳窗顯示（可選取複製），
檔案在 `%LOCALAPPDATA%\ClaudeCat\claudecat.log`（自動輪替，3×512KB）。
記錄內容：啟動參數、每次輪詢失敗原因、從錯誤恢復時間點、程式崩潰堆疊。
（刻意不用「開啟資料夾」——鎖定政策的公司電腦上 Explorer 可能拒絕導覽
`AppData\Local`，實測踩過。）

⚠️ EXE 是 `--windowed`（無主控台），`stderr` 除錯訊息會直接消失看不到——
右鍵選單狀態行和 Show log 是僅有的兩個診斷管道。

## 調整
所有可調參數在 `cat.py` 頂部常數區：
- `POLL_INTERVAL` / `POLL_CHOICES`：預設與可選輪詢間隔（秒，最低 180——
  端點限流極凶，選單刻意不提供更快的選項）
- `QUOTA_FIELD`：驅動貓速的用量欄位；`WEEKLY_FIELD`：徽章顯示的週限額欄位
- `CAT_SIZE` / `SIZE_CHOICES`：貓咪尺寸選項
- `SPEED_TABLE`：用量 % → 動畫速度映射

精靈圖設定在 `spritecat.py`：
- `WHITE_THRESHOLD`：白色背景去除閾值（純白背景圖才適用；棋盤格/非白色
  背景的圖需自行先去背存成乾淨的白底或透明 PNG 再放進 skin 資料夾）
- 檔名含 `sleep` 的圖片視為睡覺姿勢（可多幀循環），含 `_09` 的視為待命姿勢，
  兩者都會從跑步循環中排除（見 `_collect_pngs`）

**輪詢間隔勿低於 180 秒**——該端點限流極凶，且需正確 claude-code User-Agent。

## Skin（皮膚）

`skins/` 下每個子資料夾是一組皮膚，右鍵選單「Skin」可即時切換。

**新增皮膚不需要重新打包 exe**：把資料夾丟到 `ClaudeCat.exe` 旁邊即可，
例如：
```
ClaudeCat.exe 所在資料夾\
├── ClaudeCat.exe
└── skins\
    └── 新皮膚名稱\
        ├── 01.png
        └── 02.png ...
```
外部 `skins\` 資料夾優先於打包時內建的皮膚（同名時外部覆蓋）。

## 已知假設
- `QUOTA_FIELD = 'five_hour'`：假設 API 回應含此欄位；若 Anthropic 改名，
  貓會以預設速度跑步並在 stderr 印出實際可用欄位清單，改常數即可。
- token 過期時自動背景跑 `claude update` 刷新（同 usage-monitor-for-claude 做法）。

## 架構
```
claude-cat/
├── api.py        # 改自 jens-duttke/usage-monitor-for-claude (MIT)
├── cat.py        # 主程式：視窗殼、事件、右鍵選單、動畫/輪詢兩條迴圈
├── spritecat.py  # 精靈圖載入：去白背景、縮放、皮膚切換、BGRA 輸出
├── vectorcat.py  # GDI+ 向量黑貓（備用）
├── winalpha.py   # UpdateLayeredWindow 逐像素 alpha 渲染（真透明，無色鍵毛邊）
├── skins/        # 皮膚資料夾（bluecat / cowcat / ragdollcat / 自訂...）
└── frames/       # 舊版點陣素材（RunCat365，備用）
```

## 打包成 EXE
```
pip install pyinstaller
pyinstaller ClaudeCat.spec
```
產出在 `dist\ClaudeCat.exe`；`skins\` 會一併凍入 exe，但如上所述，
之後新增皮膚不需重新打包，丟到 exe 旁邊的 `skins\` 資料夾即可。

## 來源與授權
- `api.py`：改自 jens-duttke/usage-monitor-for-claude（MIT），修改處已標註
- `winalpha.py`：本專案原創，UpdateLayeredWindow 逐像素 alpha 渲染
- `vectorcat.py`：本專案原創，GDI+ 向量黑貓（已改用精靈圖，保留備用）
- `spritecat.py`：本專案原創，載入 PNG 精靈圖並處理去背/縮放/皮膚切換
- `skins/bluecat`、`skins/cowcat`、`skins/ragdollcat`：貓咪精靈圖素材
- `frames/cat_*.png`：runcat-dev/RunCat365 貓咪素材（Apache-2.0），備用
