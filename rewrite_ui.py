import re

with open('chat/chat.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Extract the script part
script_match = re.search(r'<script>([\s\S]*)</script>', content)
if not script_match:
    print("Cannot find script tag")
    exit(1)

js_content = script_match.group(1)

# Modify appendUser and appendAssistant to match the new UI style
js_content = js_content.replace("el.className = 'msg msg-user';", "el.className = 'msg msg-user';\n  el.style.display = 'flex';\n  el.style.justifyContent = 'flex-end';\n  el.style.marginBottom = '20px';")
js_content = js_content.replace("el.className = 'msg msg-assistant';", "el.className = 'msg msg-assistant';\n  el.style.display = 'flex';\n  el.style.flexDirection = 'column';\n  el.style.alignItems = 'flex-start';\n  el.style.marginBottom = '20px';")

# Adjust JS for nav tabs
js_content = js_content.replace(
    "document.getElementById('tab-' + p).classList.toggle('active', p === t);",
    "document.getElementById('nav-' + p).classList.toggle('active', p === t);\n    document.getElementById('page-' + p).style.display = (p === t) ? 'flex' : 'none';"
)


new_html = f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<title>ClaudeCat</title>
<style>
  body {{ font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; margin: 0; background: #212121; color: #ececec; font-size: 15px; height: 100vh; overflow: hidden; }}
  
  /* Sidebar */
  #sidebar {{ width: 260px; background-color: #171717; display: flex; flex-direction: column; padding: 12px; border-right: 1px solid #333; }}
  .btn-new-chat {{ background: #212121; color: #ececec; border: none; padding: 10px 14px; border-radius: 8px; cursor: pointer; text-align: left; display: flex; align-items: center; gap: 10px; transition: background 0.2s; }}
  .btn-new-chat:hover {{ background: #2f2f2f; }}
  
  .nav-item {{ background: transparent; color: #a1a1aa; border: none; padding: 10px 14px; border-radius: 8px; cursor: pointer; text-align: left; transition: background 0.2s, color 0.2s; width: 100%; margin-bottom: 4px; }}
  .nav-item:hover {{ background: #212121; color: #ececec; }}
  .nav-item.active {{ background: #2f2f2f; color: #ececec; font-weight: 500; }}
  
  select {{ background: #2f2f2f; color: #ececec; border: 1px solid #333; padding: 8px; border-radius: 6px; font-size: 13px; outline: none; }}
  
  /* Chat Area */
  .page {{ display: none; flex-direction: column; height: 100%; }}
  .page.active {{ display: flex; }}
  
  #chat-messages {{ flex: 1; overflow-y: auto; padding: 24px; padding-bottom: 140px; scroll-behavior: smooth; }}
  #chat-messages::-webkit-scrollbar {{ width: 8px; }}
  #chat-messages::-webkit-scrollbar-thumb {{ background: #555; border-radius: 4px; }}
  
  .bubble {{ display: inline-block; padding: 12px 18px; border-radius: 18px; max-width: 800px; line-height: 1.6; word-break: break-word; }}
  .msg-user .bubble {{ background: #2f2f2f; color: #ececec; border-bottom-right-radius: 4px; }}
  .msg-assistant .bubble {{ background: transparent; padding: 4px 0; color: #ececec; width: 100%; }}
  
  .msg-actions {{ display: flex; gap: 8px; margin-top: 8px; }}
  .msg-actions button {{ background: transparent; border: none; color: #888; cursor: pointer; font-size: 13px; padding: 4px; border-radius: 4px; display: flex; align-items: center; transition: background 0.2s; }}
  .msg-actions button:hover {{ background: #2f2f2f; color: #ddd; }}
  
  /* Input Area */
  .chat-input-wrapper {{ width: 100%; max-width: 768px; background: #2f2f2f; border-radius: 20px; padding: 8px 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.3); border: 1px solid #444; position: relative; }}
  .chat-input-wrapper textarea {{ flex: 1; background: transparent; color: #ececec; border: none; padding: 8px; font-family: inherit; font-size: 15px; resize: none; min-height: 24px; max-height: 200px; line-height: 1.5; outline: none; }}
  
  .icon-btn {{ background: #444; color: #ececec; border: none; border-radius: 50%; width: 32px; height: 32px; display: flex; align-items: center; justify-content: center; cursor: pointer; transition: background 0.2s; }}
  .icon-btn:hover {{ background: #555; }}
  .icon-btn:disabled {{ background: #333; color: #555; cursor: default; }}
  .icon-btn.primary {{ background: #ececec; color: #171717; }}
  .icon-btn.primary:hover {{ background: #fff; }}
  .icon-btn.primary:disabled {{ background: #555; color: #333; }}
  
  #file-preview {{ font-size: 12px; color: #a1a1aa; padding: 4px 8px; background: #3f3f46; border-radius: 12px; display: inline-block; margin-bottom: 8px; margin-left: 40px; }}
  #file-preview .remove {{ cursor: pointer; color: #f87171; margin-left: 6px; font-weight: bold; }}
  
  .typing {{ font-size: 12px; color: #a1a1aa; position: absolute; top: -25px; left: 16px; }}
  .degraded {{ font-size: 12px; color: #888; font-style: italic; margin-top: 4px; }}
  .msg-system .bubble {{ color: #a1a1aa; font-style: italic; font-size: 13px; text-align: center; width: 100%; }}
  
  /* Schedule specific */
  table {{ width: 100%; border-collapse: collapse; margin-top: 20px; font-size: 14px; }}
  td, th {{ padding: 10px; border-bottom: 1px solid #333; text-align: left; }}
  input, select {{ background: #2f2f2f; color: #ececec; border: 1px solid #444; padding: 6px 10px; border-radius: 6px; }}
  form {{ background: #171717; padding: 20px; border-radius: 12px; margin-top: 20px; border: 1px solid #333; }}
  .row {{ display: flex; gap: 12px; align-items: center; margin-bottom: 12px; }}
  .row label {{ width: 70px; color: #a1a1aa; }}
  button.primary {{ background: #ececec; color: #171717; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-weight: 500; }}
  button.primary:hover {{ background: #fff; }}
  .del {{ color: #f87171; cursor: pointer; background: transparent; border: none; }}
  .del:hover {{ text-decoration: underline; }}
  .rowline:hover {{ background: #2f2f2f; cursor: pointer; }}
</style>
</head>
<body>
<div style="display: flex; height: 100vh; background-color: #212121; color: #ececec;">
  
  <!-- Sidebar -->
  <div id="sidebar">
    <button class="btn-new-chat" onclick="clearChatHistory()">
      <span style="font-size: 18px; line-height: 1;">+</span> <span style="font-weight: 500;">新對話</span>
    </button>
    <div style="margin-top: 24px; flex-grow: 1;">
      <div style="font-size: 12px; color: #71717a; margin-bottom: 8px; padding-left: 8px; font-weight: 600;">導覽</div>
      <button class="nav-item active" id="nav-chat" onclick="showTab('chat')">💬 交談</button>
      <button class="nav-item" id="nav-schedule" onclick="showTab('schedule')">📅 定時排程</button>
    </div>
    <div class="sidebar-bottom">
       <button class="nav-item" onclick="exportChat()" style="margin-bottom: 16px;">📤 匯出對話紀錄</button>
       <div style="font-size: 12px; color: #71717a; padding: 0 8px 6px 8px; font-weight: 600;">切換模型</div>
       <select id="model-select" onchange="onModelChange()" style="width: 100%;"></select>
    </div>
  </div>
  
  <!-- Main -->
  <div style="flex: 1; display: flex; flex-direction: column; position: relative;">
    
    <!-- Chat Page -->
    <div id="page-chat" class="page active" style="position: relative;">
      <div id="chat-messages"></div>
      
      <div style="position: absolute; bottom: 0; left: 0; right: 0; background: linear-gradient(180deg, transparent, #212121 40%); padding: 24px; display: flex; justify-content: center;">
         <div class="chat-input-wrapper">
            <div id="chat-typing" class="typing" style="display:none">🐱 思考中... <span id="chat-timer">0</span>s</div>
            <div id="file-preview">📎 <span id="file-name"></span> <span class="remove" onclick="clearFile()">✕</span></div>
            <div style="display: flex; align-items: flex-end; gap: 8px;">
               <button id="chat-attach" class="icon-btn" onclick="openFile()" title="附加檔案">📎</button>
               <textarea id="chat-input" rows="1" placeholder="傳送訊息給 ClaudeCat..." onkeydown="onInputKey(event)"></textarea>
               <button id="chat-send" class="icon-btn primary" onclick="sendMessage()">⬆</button>
            </div>
         </div>
      </div>
    </div>
    
    <!-- Schedule Page -->
    <div id="page-schedule" class="page" style="padding: 32px; overflow-y: auto; display: none;">
      <h2 style="margin-top: 0; color: #ececec;">定時排程</h2>
      <div id="errors" style="color: #f87171; white-space: pre-line; margin-bottom: 12px;"></div>
      <table>
        <thead><tr><th>啟用</th><th>標題</th><th>週期</th><th>操作</th></tr></thead>
        <tbody id="list"></tbody>
      </table>

      <form onsubmit="return false">
        <h3 style="margin-top: 0; margin-bottom: 16px; color: #ececec; font-size: 15px;">新增 / 編輯排程</h3>
        <input type="hidden" id="f-id">
        <div class="row"><label>標題</label><input id="f-title" style="flex:1"></div>
        <div class="row"><label>週期</label>
          <select id="f-type" onchange="syncFields()">
            <option value="daily">每天</option>
            <option value="weekly">每星期</option>
            <option value="hourly">每小時</option>
          </select>
          <span id="f-day-wrap"><select id="f-day">
            <option>MO</option><option>TU</option><option>WE</option><option>TH</option>
            <option>FR</option><option>SA</option><option>SU</option>
          </select></span>
          <span id="f-time-wrap"><input id="f-time" type="time" value="09:00"></span>
          <span id="f-minute-wrap">第 <input id="f-minute" type="number" min="0" max="59" value="0" style="width: 60px;"> 分</span>
        </div>
        <div class="row"><label>提前警示</label>
          <div><input id="f-lead" type="number" min="0" value="0" style="width: 60px;"> 分鐘 <span style="color: #71717a; font-size: 12px;">(0 代表僅正點觸發)</span></div>
        </div>
        <div class="row" style="margin-top: 20px;">
          <button class="primary" onclick="submitForm()" id="f-submit">新增排程</button>
          <button onclick="resetForm()" style="background:#3f3f46;color:#ececec;border:0;padding:8px 16px;border-radius:6px;cursor:pointer">清空</button>
          <span id="f-msg" style="color: #a1a1aa; margin-left: 10px;"></span>
        </div>
      </form>
    </div>
  </div>
</div>

<script>
{js_content}
</script>
</body>
</html>
"""

with open('chat/chat.html', 'w', encoding='utf-8') as f:
    f.write(new_html)
print("Updated chat.html!")
