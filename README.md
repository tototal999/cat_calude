# ClaudeCat

桌面向量貓，跑速反映 Claude 5 小時 session 用量。

## 需求
- Windows 10/11、Python 3.10+（含 tkinter，官方安裝包預設就有）
- `pip install requests`（貓咪本體是 GDI+ 向量繪製，不需要 Pillow 或圖片素材）
- Claude Code 已登入（讀取 `~/.claude/.credentials.json`）

## 執行
```
python cat.py
```
- 左鍵拖曳移動（貓或 % 徽章皆可）
- 右鍵選單：百分比 / 手動刷新 / 置頂切換 / 顯示%開關 / Size（64-160px）/
  Face right（朝向切換）/ 結束
- 貓下方預設顯示用量 % 徽章（含 session 重置時間，錯誤時變紅色 `!`），
  可從右鍵選單關閉
- 用量 0-25% 散步 → 25-50% 小跑 → 50-75% 快跑 → 75-95% 狂奔 →
  >95% 或 API 錯誤時靜止（站立姿勢）

## 調整
所有可調參數在 `cat.py` 頂部常數區：
- `POLL_INTERVAL`：輪詢間隔（秒）
- `QUOTA_FIELD`：驅動貓速的用量欄位
- `CAT_SIZE` / `CAT_COLOR` / `EYE_COLOR` / `RUN_FRAMES` / `SIZE_CHOICES`：向量貓外觀
- `SPEED_TABLE`：用量 % → 動畫速度映射

**輪詢間隔勿低於 180 秒**——該端點限流極凶，且需正確 claude-code User-Agent。

## 已知假設
- `QUOTA_FIELD = 'five_hour'`：假設 API 回應含此欄位；若 Anthropic 改名，
  貓會靜止並在 stderr 印出實際可用欄位清單，改常數即可。
- token 過期時自動背景跑 `claude update` 刷新（同 usage-monitor-for-claude 做法）。

## 架構
```
claude-cat/
├── api.py        # 改自 jens-duttke/usage-monitor-for-claude (MIT)
├── cat.py        # 主程式：視窗殼、事件、右鍵選單、動畫/輪詢兩條迴圈
├── vectorcat.py  # GDI+ 向量貓：曲線定義、參數化跑步循環、眼睛/鬍鬚
├── winalpha.py   # UpdateLayeredWindow 逐像素 alpha 渲染（真透明，無色鍵毛邊）
└── frames/       # RunCat365 點陣素材 (Apache-2.0)，已停用、保留備援
```

## 來源與授權
- `api.py`：改自 jens-duttke/usage-monitor-for-claude（MIT），修改處已標註
- `winalpha.py`：本專案原創，UpdateLayeredWindow 逐像素 alpha 渲染
  （取代 tkinter `-transparentcolor` 色鍵去背，抗鋸齒邊緣不再有毛邊）
- `vectorcat.py`：本專案原創，GDI+ 向量貓（曲線定義、參數化跑步循環），
  尺寸/顏色/幀數由 `cat.py` 頂部常數調整，執行中亦可從右鍵選單即時調整
- `frames/`：runcat-dev/RunCat365 貓咪素材（Apache-2.0）——已改用向量貓，
  此資料夾目前未使用，保留備援
