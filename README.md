# ClaudeCat

桌面藍貓寵物，跑速反映 Claude 5 小時 session 用量。

## 需求
- Windows 10/11、Python 3.10+（含 tkinter，官方安裝包預設就有）
- `pip install requests Pillow`
- Claude Code 已登入（讀取 `~/.claude/.credentials.json`）

## 執行
```
python cat.py
```
- 左鍵拖曳移動（貓或 % 徽章皆可）
- 右鍵選單：百分比 / 手動刷新 / 置頂切換 / 顯示%開關 / Size（64-256px）/
  Face right（朝向切換）/ 結束
- 貓下方預設顯示用量 % 徽章（含 session 重置時間，錯誤時變紅色 `!`），
  可從右鍵選單關閉
- **超過 90% 使用率時，徽章文字變為紅色警示**
- 用量 0-25% 散步 → 25-50% 小跑 → 50-75% 快跑 → 75-95% 狂奔 →
  >95% 靜止（站立姿勢）；API 無法連線時以預設速度播放動畫

## 調整
所有可調參數在 `cat.py` 頂部常數區：
- `POLL_INTERVAL`：輪詢間隔（秒）
- `QUOTA_FIELD`：驅動貓速的用量欄位
- `CAT_SIZE` / `SIZE_CHOICES`：貓咪尺寸選項
- `SPEED_TABLE`：用量 % → 動畫速度映射

藍貓精靈圖設定在 `spritecat.py`：
- `SPRITE_PATTERN` / `SPRITE_COUNT`：幀檔名格式與數量
- `WHITE_THRESHOLD`：白色背景去除閾值

**輪詢間隔勿低於 180 秒**——該端點限流極凶，且需正確 claude-code User-Agent。

## 已知假設
- `QUOTA_FIELD = 'five_hour'`：假設 API 回應含此欄位；若 Anthropic 改名，
  貓會以預設速度跑步並在 stderr 印出實際可用欄位清單，改常數即可。
- token 過期時自動背景跑 `claude update` 刷新（同 usage-monitor-for-claude 做法）。

## 架構
```
claude-cat/
├── api.py        # 改自 jens-duttke/usage-monitor-for-claude (MIT)
├── cat.py        # 主程式：視窗殼、事件、右鍵選單、動畫/輪詢兩條迴圈
├── spritecat.py  # 藍貓精靈圖載入：去白背景、縮放、BGRA 輸出
├── vectorcat.py  # GDI+ 向量黑貓（備用）
├── winalpha.py   # UpdateLayeredWindow 逐像素 alpha 渲染（真透明，無色鍵毛邊）
└── frames/       # bluecat01-06.png 藍貓精靈圖 + 舊版點陣素材
```

## 來源與授權
- `api.py`：改自 jens-duttke/usage-monitor-for-claude（MIT），修改處已標註
- `winalpha.py`：本專案原創，UpdateLayeredWindow 逐像素 alpha 渲染
- `vectorcat.py`：本專案原創，GDI+ 向量黑貓（已改用精靈圖，保留備用）
- `spritecat.py`：本專案原創，載入 PNG 精靈圖並處理去背/縮放/格式轉換
- `frames/bluecat*.png`：藍貓精靈圖素材
- `frames/cat_*.png`：runcat-dev/RunCat365 貓咪素材（Apache-2.0），備用
