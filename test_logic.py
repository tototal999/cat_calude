import json
import time
from datetime import datetime, timedelta
from pathlib import Path
import os
import shutil

import scheduler as scheduler_mod
import api
import llm

def test_scheduler_bad_json():
    print("[1] 測試 schedule.json 壞格式處理")
    test_file = Path('test_schedule.json')
    test_file.write_text('{"bad json', encoding='utf-8')
    s = scheduler_mod.Scheduler(test_file)
    if len(s.errors) > 0 and '解析失敗' in s.errors[0]:
        print("  ✅ 成功攔截壞格式 JSON，未崩潰")
    else:
        print("  ❌ 壞格式攔截失敗")
    
    test_file.write_text('[{ "id": "123", "title": "Missing type" }]', encoding='utf-8')
    s = scheduler_mod.Scheduler(test_file)
    if len(s.errors) > 0 and 'Missing type' in s.errors[0]:
        print("  ✅ 成功攔截格式錯誤的單筆紀錄，未崩潰")
    else:
        print("  ❌ 格式錯誤紀錄攔截失敗", s.errors)
    test_file.unlink()


def test_scheduler_triggers():
    print("\n[2] 測試排程觸發邏輯 (daily / weekly / hourly)")
    test_file = Path('test_schedule.json')
    now = datetime.now()
    
    # 建立 2 分鐘後的 daily，提前 1 分鐘
    t2 = now + timedelta(minutes=2)
    s_time = t2.strftime('%H:%M')
    
    # 建立目前分鐘的 hourly
    s_min = now.minute
    
    data = [
        {
            "id": "t1", "title": "Daily Test", "type": "daily",
            "time": s_time, "lead_min": 1, "enabled": True
        },
        {
            "id": "t2", "title": "Hourly Test", "type": "hourly",
            "minute": s_min, "lead_min": 0, "enabled": True
        },
        {
            "id": "t3", "title": "Disabled", "type": "daily",
            "time": s_time, "lead_min": 1, "enabled": False
        }
    ]
    test_file.write_text(json.dumps(data), encoding='utf-8')
    s = scheduler_mod.Scheduler(test_file)
    
    # 模擬 1 分鐘後 (應該觸發 daily 的提前卡)
    fake_now_1m = now + timedelta(minutes=1)
    popups = s.tick(fake_now_1m)
    found_lead = any(p[0]['id'] == 't1' and p[1] == 'lead' for p in popups)
    if found_lead:
        print("  ✅ 成功觸發 1 分鐘前提前卡 (daily)")
    else:
        print("  ❌ 提前卡觸發失敗")
        
    # 模擬 2 分鐘後 (應該觸發 daily 的正點卡)
    fake_now_2m = now + timedelta(minutes=2)
    popups = s.tick(fake_now_2m)
    found_ontime = any(p[0]['id'] == 't1' and p[1] == 'ontime' for p in popups)
    if found_ontime:
        print("  ✅ 成功觸發正點卡 (daily)")
    else:
        print("  ❌ 正點卡觸發失敗")
        
    # 確認 Disabled 沒被觸發
    found_disabled = any(p[0]['id'] == 't3' for p in popups)
    if not found_disabled:
        print("  ✅ 成功忽略未啟用 (enabled=false) 的排程")
    else:
        print("  ❌ 未啟用的排程被觸發了")
        
    # 確認 Hourly 觸發
    popups = s.tick(now)
    found_hourly = any(p[0]['id'] == 't2' for p in popups)
    if found_hourly:
        print("  ✅ 成功觸發 hourly 排程")
    else:
        print("  ❌ Hourly 觸發失敗")
        
    test_file.unlink()


def test_api_credentials():
    print("\n[3] 測試 API 憑證毀損與恢復")
    cred_path = Path.home() / '.claude' / '.credentials.json'
    backup_path = Path.home() / '.claude' / '.credentials.json.bak'
    
    # 備份原始憑證
    if cred_path.exists():
        shutil.copy(cred_path, backup_path)
    
    try:
        # 測試 1：沒有憑證檔
        if cred_path.exists():
            cred_path.unlink()
        res = api.fetch_usage()
        if 'error' in res and 'No OAuth token' in res['error']:
            print("  ✅ 成功偵測憑證遺失")
        else:
            print("  ❌ 憑證遺失偵測失敗", res)
            
        # 測試 2：憑證內容損毀
        cred_path.parent.mkdir(parents=True, exist_ok=True)
        cred_path.write_text('bad data', encoding='utf-8')
        res = api.fetch_usage()
        if 'error' in res and 'No OAuth token' in res['error']:
            print("  ✅ 成功偵測憑證格式損毀")
        else:
            print("  ❌ 憑證損毀偵測失敗", res)
            
    finally:
        # 復原憑證
        if backup_path.exists():
            shutil.copy(backup_path, cred_path)
            backup_path.unlink()
            res = api.fetch_usage()
            if 'error' not in res:
                print("  ✅ 憑證復原後，API 呼叫成功恢復正常")
            else:
                print("  ⚠ 憑證復原後 API 仍回傳錯誤 (可能 token 過期或 rate limit)")
        else:
            print("  ⚠ 無法復原憑證：無備份檔")

def test_llm_logic():
    print("\n[4] 測試 LLM 模組基礎邏輯 (Part 2)")
    
    # 測試 1: Context overflow 偵測
    if llm._looks_like_context_overflow("Maximum context length exceeded"):
        print("  ✅ 成功偵測 context overflow 關鍵字")
    else:
        print("  ❌ context overflow 偵測失敗")
        
    # 測試 2: Model list (去重與 fallback)
    old_config = getattr(llm, '_config', {})
    llm._config = {
        'model': 'primary-model',
        'fallback_models': ['fallback-1', 'primary-model', 'fallback-2']
    }
    models = llm.list_models()
    if models == ['primary-model', 'fallback-1', 'fallback-2']:
        print("  ✅ 成功合併模型清單並去重")
    else:
        print("  ❌ 模型清單合併錯誤:", models)
        
    # 測試 3: 匯出功能
    llm._config['export_dir'] = 'test_export'
    Path('test_export').mkdir(exist_ok=True)
    try:
        p1 = llm.save_note("測試筆記", "test-model")
        if p1.exists():
            print("  ✅ 單篇筆記存檔成功")
            p1.unlink()
        else:
            print("  ❌ 單篇筆記存檔失敗")
            
        p2 = llm.export_chat([{"role":"user", "content":"hi"}], "test-model")
        if p2.exists():
            print("  ✅ 完整對話匯出成功")
            p2.unlink()
        else:
            print("  ❌ 完整對話匯出失敗")
    finally:
        llm._config = old_config
        try:
            Path('test_export').rmdir()
        except OSError:
            pass

if __name__ == '__main__':
    print("=== ClaudeCat 自動化邏輯驗證 ===")
    test_scheduler_bad_json()
    test_scheduler_triggers()
    test_api_credentials()
    test_llm_logic()
    print("================================")
