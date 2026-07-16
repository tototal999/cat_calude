# ClaudeCat 需求文件

## 1. 目的

在 Windows 桌面顯示一隻會跑的貓，跑速對應 Claude 5 小時 session 用量百分比，取代單純看數字/進度條的用量監控方式。

## 2. 核心假設

| # | 假設 | 驗證狀態 |
|---|---|---|
| 1 | API 端點 `GET https://api.anthropic.com/api/oauth/usage`，Bearer token 讀自 `~/.claude/.credentials.json` | 待你在 Windows 用 `python -c "import api; print(api.fetch_usage())"` 實測確認 |
| 2 | 回應中驅動貓速的欄位是 `five_hour`（`QUOTA_FIELD` 常數） | 待實測，若欄位名不對貓會靜止 + stderr 印出實際欄位清單 |
| 3 | 該端點限流極凶，需正確 `User-Agent: claude-code/<version>` header，輪詢間隔不可低於 180 秒 | 已在 `api.py` 實作（動態抓 `claude --version`），長跑穩定性待你 1 小時實測 |
| 4 | token 過期時背景跑 `claude update` 可自動刷新 | 沿用 usage-monitor-for-claude 已驗證的做法，未獨立測試 |

## 3. 範圍

**做**：桌面置頂透明視窗、向量貓動畫（8 幀跑步循環+站立幀，含眼睛/鬍鬚）、用量→速度映射、拖曳移動、右鍵選單（顯示%/手動刷新/置頂切換/顯示%開關/大小 64-160px/朝向切換/結束）、貓下方 % 徽章含 session 重置時間（錯誤時紅色 `!`）、錯誤時靜止並顯示原因、可打包成單一 exe

**不做（YAGNI，明確排除）**：多寵物、設定 GUI、開機自啟整合（手動拖捷徑到 `shell:startup` 即可）、多用量欄位同時顯示（weekly 只在右鍵選單文字裡帶出，不影響貓速）

## 4. 架構

```
claude-cat/
├── api.py     # 改自 jens-duttke/usage-monitor-for-claude (MIT)
│              # 修改：移除 .i18n / .claude_cli 依賴，改內嵌字串表 + 直接呼叫 claude --version
├── cat.py     # 主程式，~230 行，tkinter（視窗殼/事件/選單）
│              # 兩條獨立迴圈：動畫 loop（每 N ms 換幀）+ 輪詢 loop（每 180s fetch）
├── winalpha.py # 純 stdlib：UpdateLayeredWindow 逐像素 alpha 渲染
│              # （2026-07-16 取代 -transparentcolor 色鍵：色鍵無法處理抗鋸齒
│              #   半透明邊緣像素，實測會留下洋紅毛邊）
├── vectorcat.py # 純 stdlib：GDI+ 向量貓，跑步循環參數化生成（8 幀 + 站立幀）
│              # （2026-07-16 取代點陣素材：可任意調 CAT_SIZE/CAT_COLOR 不失真）
└── frames/    # RunCat365 素材 (Apache-2.0)——已停用，保留備援；
               # winalpha.load_rgba/to_premultiplied_bgra 亦僅供 PNG 備援路徑使用
```

## 5. 用量 → 速度映射（`SPEED_TABLE`，可調）

| Session 用量 | 幀間隔 | 語意 |
|---|---|---|
| 0–25% | 400ms | 散步 |
| 25–50% | 250ms | 小跑 |
| 50–75% | 150ms | 快跑 |
| 75–95% | 80ms | 狂奔 |
| >95% / 錯誤 / token失效 | 靜止 | 明確告警，不裝沒事 |

## 6. 配置參數（在 `cat.py` 頂部常數，無外部設定檔）

- `POLL_INTERVAL = 180`（秒，硬性下限）
- `QUOTA_FIELD = 'five_hour'`
- `CAT_SIZE = 96`（啟動值，執行中可由右鍵選單改）/ `CAT_COLOR` / `EYE_COLOR` /
  `RUN_FRAMES = 8` / `SIZE_CHOICES = (64, 96, 128, 160)`（向量貓外觀）
- `SPEED_TABLE`

## 7. 已驗證（容器內 QA，11 項 PASS）

速度映射（含邊界值與 >95% 凍結）、錯誤狀態凍結、輪詢狀態機（正常/429退避）— 測試方式：`QA_RESULT|STATUS:|EXPECTED:|ACTUAL:` 格式，mock `api.fetch_usage()`。

## 8. Windows 實機驗證結果（2026-07-16）

- ~~`-transparentcolor` 去背~~ → 實測有洋紅毛邊（幀圖含 1,500+ 半透明像素/幀），
  已改用 `winalpha.py` UpdateLayeredWindow 逐像素 alpha，實測邊緣平滑無毛邊
- API 端點 + `five_hour` 欄位：實測 PASS（回傳 utilization/resets_at 正常）
- 連續輪詢 210 秒（跨兩次 poll）：無 429、stderr 乾淨；1 小時長跑由日常使用驗證
- 拖曳（layered window 事件路徑）：實測正常
- 仍未驗證：token 過期→自動刷新完整流程、PyInstaller 打包後 `sys._MEIPASS` 路徑

## 9. 打包（PyInstaller，需在 Windows 上執行，容器無法 cross-compile）

```
pip install pyinstaller
pyinstaller --onefile --windowed --name ClaudeCat cat.py
# （改用向量貓後不再需要 --add-data "frames;frames"）
```

## 10. 已知限制 / 技術負債

- `QUOTA_FIELD` 是猜測值，非官方文件確認，Anthropic 若改欄位名會直接讓貓靜止（設計上是 fail-loud，不是 fail-silent）
- 未做開機自啟、未簽章 exe（Defender 首次執行會跳警告）
- 單帳號設計，未支援 usage-monitor-for-claude 的多帳號輪詢