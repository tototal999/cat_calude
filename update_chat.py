import os

new_html = """<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<title>ClaudeCat</title>
<!-- Include Highlight.js -->
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.8.0/styles/github-dark.min.css">
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.8.0/highlight.min.js"></script>
<style>
  body { font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; margin: 0; background: #343541; color: #ececec; font-size: 15px; height: 100vh; overflow: hidden; }
  
  /* Sidebar */
  #sidebar { width: 260px; background-color: #202123; display: flex; flex-direction: column; padding: 12px; border-right: 1px solid #333; transition: width 0.3s ease; }
  .btn-new-chat { background: transparent; border: 1px solid #444; color: #ececec; padding: 12px 14px; border-radius: 6px; cursor: pointer; text-align: left; display: flex; align-items: center; gap: 12px; transition: background 0.2s; font-size: 14px; }
  .btn-new-chat:hover { background: #2A2B32; }
  
  .nav-item { background: transparent; color: #ececec; border: none; padding: 12px 14px; border-radius: 6px; cursor: pointer; text-align: left; transition: background 0.2s; width: 100%; margin-bottom: 4px; display: flex; align-items: center; justify-content: space-between; font-size: 14px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .nav-item:hover { background: #2A2B32; }
  .nav-item.active { background: #343541; }
  .nav-item .del-btn { display: none; color: #888; background: transparent; border: none; cursor: pointer; padding: 4px; border-radius: 4px; }
  .nav-item:hover .del-btn { display: block; }
  .nav-item .del-btn:hover { color: #f87171; background: #444; }
  
  select { background: #343541; color: #ececec; border: 1px solid #555; padding: 8px; border-radius: 6px; font-size: 13px; outline: none; }
  
  /* Chat Area */
  .page { display: none; flex-direction: column; height: 100%; }
  .page.active { display: flex; }
  
  #chat-messages { flex: 1; overflow-y: auto; padding: 0; padding-bottom: 160px; scroll-behavior: smooth; }
  #chat-messages::-webkit-scrollbar { width: 8px; }
  #chat-messages::-webkit-scrollbar-thumb { background: #555; border-radius: 4px; }
  
  .msg { width: 100%; border-bottom: 1px solid rgba(0,0,0,0.1); padding: 24px 0; display: flex; justify-content: center; }
  .msg-user { background: #343541; }
  .msg-assistant { background: #444654; }
  .msg-content { max-width: 800px; width: 100%; display: flex; gap: 24px; padding: 0 24px; }
  .avatar { width: 30px; height: 30px; border-radius: 4px; display: flex; align-items: center; justify-content: center; font-size: 18px; flex-shrink: 0; }
  .avatar-user { background: #5436DA; }
  .avatar-ai { background: #10a37f; }
  .bubble { flex: 1; line-height: 1.6; word-break: break-word; color: #ececec; }
  
  .msg-actions { display: flex; gap: 8px; margin-top: 12px; }
  .msg-actions button { background: transparent; border: none; color: #888; cursor: pointer; font-size: 16px; padding: 4px; border-radius: 4px; display: flex; align-items: center; transition: color 0.2s; }
  .msg-actions button:hover { color: #ececec; }
  
  /* Input Area */
  .chat-input-wrapper { width: 100%; max-width: 800px; background: #40414f; border-radius: 12px; padding: 8px 16px; box-shadow: 0 0 15px rgba(0,0,0,0.1); border: 1px solid rgba(32,33,35,.5); position: relative; margin: 0 auto; }
  .chat-input-wrapper textarea { flex: 1; background: transparent; color: #ececec; border: none; padding: 12px 0; font-family: inherit; font-size: 15px; resize: none; min-height: 24px; max-height: 200px; line-height: 1.5; outline: none; }
  
  .icon-btn { background: transparent; color: #888; border: none; border-radius: 6px; width: 36px; height: 36px; display: flex; align-items: center; justify-content: center; cursor: pointer; transition: background 0.2s; font-size: 18px; }
  .icon-btn:hover { background: #2A2B32; color: #ececec; }
  .icon-btn:disabled { color: #555; cursor: default; background: transparent; }
  .icon-btn.primary { background: #10a37f; color: white; border-radius: 6px; margin-bottom: 4px; }
  .icon-btn.primary:hover { background: #1a7f64; }
  .icon-btn.primary:disabled { background: transparent; color: #555; }
  
  #file-preview { font-size: 12px; color: #a1a1aa; padding: 6px 10px; background: #202123; border-radius: 8px; display: inline-block; margin-bottom: 12px; }
  #file-preview .remove { cursor: pointer; color: #f87171; margin-left: 8px; font-weight: bold; font-size: 14px; }
  
  .typing { font-size: 12px; color: #a1a1aa; position: absolute; top: -25px; left: 0; }
  
  /* Markdown specific */
  pre { background: #000; color: #d4d4d4; padding: 16px; border-radius: 6px; overflow-x: auto; font-family: Consolas, monospace; font-size: 13px; margin: 16px 0; }
  .code-header { display: flex; justify-content: space-between; align-items: center; background: #343541; padding: 6px 16px; border-top-left-radius: 6px; border-top-right-radius: 6px; margin-bottom: -16px; position: relative; z-index: 10; font-size: 12px; color: #b4b4b4; font-family: sans-serif; border-bottom: 1px solid #555; }
  .code-header button { background: transparent; border: none; color: #b4b4b4; cursor: pointer; display: flex; align-items: center; gap: 6px; font-size: 12px; }
  .code-header button:hover { color: #ececec; }
  
  /* Slash Command Prompts Dropdown */
  #prompts-dropdown { position: absolute; bottom: 100%; left: 0; width: 100%; max-height: 200px; overflow-y: auto; background: #202123; border: 1px solid #444; border-radius: 8px; display: none; z-index: 1000; box-shadow: 0 4px 12px rgba(0,0,0,0.5); }
  .prompt-item { padding: 10px 16px; cursor: pointer; color: #ececec; border-bottom: 1px solid #333; }
  .prompt-item:hover, .prompt-item.selected { background: #2A2B32; }
  .prompt-title { font-weight: bold; margin-bottom: 4px; font-size: 14px; }
  .prompt-desc { font-size: 12px; color: #888; }
  
  /* Schedule specific */
  table { width: 100%; border-collapse: collapse; margin-top: 20px; font-size: 14px; }
  td, th { padding: 10px; border-bottom: 1px solid #444; text-align: left; }
  input, select { background: #40414f; color: #ececec; border: 1px solid #555; padding: 8px 10px; border-radius: 6px; }
  form { background: #202123; padding: 24px; border-radius: 12px; margin-top: 20px; border: 1px solid #444; }
  .row { display: flex; gap: 12px; align-items: center; margin-bottom: 16px; }
  .row label { width: 70px; color: #a1a1aa; }
  button.primary { background: #10a37f; color: white; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-weight: 500; }
  button.primary:hover { background: #1a7f64; }
  .del { color: #f87171; cursor: pointer; background: transparent; border: none; }
  .del:hover { text-decoration: underline; }
  .rowline:hover { background: #40414f; cursor: pointer; }
</style>
</head>
<body>
<div style="display: flex; height: 100vh; background-color: #343541; color: #ececec; position: relative;">
  
  <!-- Sidebar -->
  <div id="sidebar">
    <button class="btn-new-chat" onclick="newChat()">
      <span style="font-size: 20px;">+</span> <span style="font-weight: 500;">New chat</span>
    </button>
    <div style="margin-top: 24px; flex-grow: 1; display: flex; flex-direction: column;">
      <div style="font-size: 12px; color: #888; margin-bottom: 8px; padding-left: 8px; font-weight: 600;">History</div>
      <div id="session-list" style="flex: 1; overflow-y: auto;">
        <!-- History items loaded dynamically -->
      </div>
    </div>
    <div class="sidebar-bottom" style="border-top: 1px solid #444; padding-top: 12px;">
       <button class="nav-item" id="nav-schedule" onclick="showTab('schedule')">📅 Schedule</button>
       <button class="nav-item" onclick="exportChat()">📤 Export History</button>
    </div>
  </div>
  
  <!-- Main -->
  <div style="flex: 1; display: flex; flex-direction: column; position: relative; min-width: 0;">
    
    <!-- Top Header -->
    <div style="height: 56px; border-bottom: 1px solid rgba(0,0,0,0.1); display: flex; align-items: center; justify-content: center; position: relative;">
        <button class="icon-btn" style="position: absolute; left: 12px;" onclick="toggleSidebar()" title="Toggle Sidebar">☰</button>
        <select id="model-select" onchange="onModelChange()" style="background: transparent; border: none; font-weight: bold; font-size: 16px; cursor: pointer; appearance: none; padding-right: 20px;"></select>
    </div>
    
    <!-- Chat Page -->
    <div id="page-chat" class="page active" style="position: relative;">
      <div id="chat-messages"></div>
      
      <div style="position: absolute; bottom: 0; left: 0; right: 0; background: linear-gradient(180deg, transparent, #343541 30%); padding: 24px; padding-bottom: 36px; display: flex; justify-content: center;">
         <div style="width: 100%; max-width: 800px; position: relative;">
            <div id="chat-typing" class="typing" style="display:none">🐱 Thinking... <span id="chat-timer">0</span>s</div>
            <div id="prompts-dropdown"></div>
            <div id="file-preview" style="display:none;">📎 <span id="file-name"></span> <span class="remove" onclick="clearFile()">✕</span></div>
            <div class="chat-input-wrapper" style="display: flex; align-items: flex-end; gap: 8px;">
               <button id="chat-attach" class="icon-btn" onclick="openFile()" title="Attach File">📎</button>
               <textarea id="chat-input" rows="1" placeholder="Send a message... (Type '/' for templates)" onkeydown="onInputKey(event)" oninput="handleInput()"></textarea>
               <button id="chat-send" class="icon-btn primary" onclick="sendMessage()">➤</button>
            </div>
            <div style="text-align: center; font-size: 11px; color: #888; margin-top: 12px;">ClaudeCat AI. Check specs for exact usage limits.</div>
         </div>
      </div>
    </div>
    
    <!-- Schedule Page -->
    <div id="page-schedule" class="page" style="padding: 40px; overflow-y: auto; display: none; max-width: 800px; margin: 0 auto; width: 100%;">
      <h2 style="margin-top: 0; color: #ececec;">Schedule Configuration</h2>
      <div id="errors" style="color: #f87171; white-space: pre-line; margin-bottom: 12px;"></div>
      <table>
        <thead><tr><th>Status</th><th>Title</th><th>Interval</th><th>Action</th></tr></thead>
        <tbody id="list"></tbody>
      </table>

      <form onsubmit="return false">
        <h3 style="margin-top: 0; margin-bottom: 16px; color: #ececec; font-size: 15px;">New / Edit Rule</h3>
        <input type="hidden" id="f-id">
        <div class="row"><label>Title</label><input id="f-title" style="flex:1"></div>
        <div class="row"><label>Cycle</label>
          <select id="f-type" onchange="syncFields()">
            <option value="daily">Daily</option>
            <option value="weekly">Weekly</option>
            <option value="hourly">Hourly</option>
          </select>
          <span id="f-day-wrap"><select id="f-day">
            <option>MO</option><option>TU</option><option>WE</option><option>TH</option>
            <option>FR</option><option>SA</option><option>SU</option>
          </select></span>
          <span id="f-time-wrap"><input id="f-time" type="time" value="09:00"></span>
          <span id="f-minute-wrap">Minute <input id="f-minute" type="number" min="0" max="59" value="0" style="width: 60px;"></span>
        </div>
        <div class="row"><label>Lead Time</label>
          <div><input id="f-lead" type="number" min="0" value="0" style="width: 60px;"> minutes <span style="color: #888; font-size: 12px;">(0 = trigger on exact time only)</span></div>
        </div>
        <div class="row" style="margin-top: 20px;">
          <button class="primary" onclick="submitForm()" id="f-submit">Save Rule</button>
          <button onclick="resetForm()" style="background:transparent;color:#ececec;border:1px solid #555;padding:8px 16px;border-radius:6px;cursor:pointer">Clear</button>
          <span id="f-msg" style="color: #a1a1aa; margin-left: 10px;"></span>
        </div>
      </form>
    </div>
  </div>
</div>

<script>
let _chatInited = false;
let _composing = false;
let _sending = false;
let _attachedFile = null;
let _currentSessionId = null;
let _timerId = null;

// Fake Prompts Library for "/"
const PROMPTS = [
  {title: 'Translate to English', desc: 'Translate the following text to professional English.', content: 'Please translate the following text to professional English:\\n\\n'},
  {title: 'Code Review', desc: 'Review the following code and suggest improvements.', content: 'Please review the following code, point out any bugs or security issues, and suggest improvements:\\n\\n'},
  {title: 'Summarize', desc: 'Provide a brief summary of the text.', content: 'Please provide a brief summary of the following text:\\n\\n'}
];
let promptSelectedIndex = 0;

function showTab(t) {
  document.getElementById('page-chat').classList.remove('active');
  document.getElementById('page-schedule').classList.remove('active');
  document.getElementById('page-' + t).classList.add('active');
  if (t === 'chat' && !_chatInited) initChat();
}

function toggleSidebar() {
  const sb = document.getElementById('sidebar');
  sb.style.display = sb.style.display === 'none' ? 'flex' : 'none';
}

function loadSessions() {
  pywebview.api.list_sessions().then(sessions => {
    const list = document.getElementById('session-list');
    list.innerHTML = '';
    sessions.forEach(s => {
      const btn = document.createElement('button');
      btn.className = 'nav-item' + (s.id === _currentSessionId ? ' active' : '');
      btn.innerHTML = `<span>💬 ${s.title}</span><span class="del-btn" title="Delete">🗑️</span>`;
      btn.onclick = (e) => {
        if (e.target.closest('.del-btn')) {
          e.stopPropagation();
          pywebview.api.delete_session(s.id).then(() => {
            if (s.id === _currentSessionId) newChat();
            else loadSessions();
          });
        } else {
          loadSession(s.id);
        }
      };
      list.appendChild(btn);
    });
  });
}

function loadSession(id) {
  pywebview.api.load_session(id).then(r => {
    if (r.error) return alert(r.error);
    _currentSessionId = id;
    showTab('chat');
    clearMessagesUI();
    r.history.forEach(msg => {
      if (msg.role === 'user') appendUserUI(msg.content);
      else if (msg.role === 'assistant') appendAssistantUI(msg.content);
    });
    if (r.model) document.getElementById('model-select').value = r.model;
    loadSessions(); // update active state
    scrollBottom();
  });
}

function newChat() {
  pywebview.api.clear_history().then(() => {
    _currentSessionId = null;
    clearMessagesUI();
    loadSessions();
    showTab('chat');
  });
}

function initChat() {
  _chatInited = true;
  pywebview.api.list_models().then(models => {
    const sel = document.getElementById('model-select');
    sel.innerHTML = '';
    models.forEach(m => {
      const opt = document.createElement('option');
      opt.value = m; opt.textContent = m;
      sel.appendChild(opt);
    });
    pywebview.api.current_model().then(cur => { sel.value = cur; });
  });
  
  loadSessions();
  
  const ta = document.getElementById('chat-input');
  ta.addEventListener('compositionstart', () => { _composing = true; });
  ta.addEventListener('compositionend', () => { _composing = false; });
  ta.addEventListener('input', () => autoResize(ta));
}

function autoResize(ta) {
  ta.style.height = 'auto';
  ta.style.height = Math.min(ta.scrollHeight, 200) + 'px';
}

function handleInput() {
  const ta = document.getElementById('chat-input');
  const dd = document.getElementById('prompts-dropdown');
  const val = ta.value;
  if (val.startsWith('/')) {
    const q = val.substring(1).toLowerCase();
    const filtered = PROMPTS.filter(p => p.title.toLowerCase().includes(q));
    if (filtered.length > 0) {
      dd.style.display = 'block';
      dd.innerHTML = '';
      filtered.forEach((p, i) => {
        const div = document.createElement('div');
        div.className = 'prompt-item' + (i === promptSelectedIndex ? ' selected' : '');
        div.innerHTML = `<div class="prompt-title">${p.title}</div><div class="prompt-desc">${p.desc}</div>`;
        div.onclick = () => {
          ta.value = p.content;
          dd.style.display = 'none';
          ta.focus();
          autoResize(ta);
        };
        dd.appendChild(div);
      });
    } else {
      dd.style.display = 'none';
    }
  } else {
    dd.style.display = 'none';
  }
}

function onInputKey(e) {
  const dd = document.getElementById('prompts-dropdown');
  if (dd.style.display === 'block') {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      const items = dd.querySelectorAll('.prompt-item');
      if (items.length === 0) return;
      items[promptSelectedIndex].classList.remove('selected');
      if (e.key === 'ArrowDown') promptSelectedIndex = (promptSelectedIndex + 1) % items.length;
      else promptSelectedIndex = (promptSelectedIndex - 1 + items.length) % items.length;
      items[promptSelectedIndex].classList.add('selected');
      items[promptSelectedIndex].scrollIntoView({block: 'nearest'});
      return;
    }
    if (e.key === 'Enter') {
      e.preventDefault();
      dd.querySelectorAll('.prompt-item')[promptSelectedIndex].click();
      return;
    }
  }
  
  if (e.key === 'Enter' && !e.shiftKey && !_composing) {
    e.preventDefault();
    sendMessage();
  }
}

function onModelChange() {
  const m = document.getElementById('model-select').value;
  pywebview.api.set_model(m);
}

function openFile() {
  pywebview.api.open_file_dialog().then(path => {
    if (path) {
      _attachedFile = path;
      document.getElementById('file-name').textContent = path.split('\\\\').pop().split('/').pop();
      document.getElementById('file-preview').style.display = 'inline-block';
    }
  });
}

function clearFile() {
  _attachedFile = null;
  document.getElementById('file-preview').style.display = 'none';
}

function sendMessage() {
  if (_sending) return;
  const ta = document.getElementById('chat-input');
  const text = ta.value.trim();
  if (!text) return;

  _sending = true;
  document.getElementById('chat-send').disabled = true;
  ta.value = '';
  autoResize(ta);
  document.getElementById('prompts-dropdown').style.display = 'none';

  appendUserUI(text + (_attachedFile ? '\\n[📎 ' + document.getElementById('file-name').textContent + ']' : ''));
  document.getElementById('chat-typing').style.display = 'block';
  
  const timerSpan = document.getElementById('chat-timer');
  timerSpan.textContent = '0';
  let elapsed = 0;
  _timerId = setInterval(() => { elapsed++; timerSpan.textContent = elapsed; }, 1000);
  scrollBottom();

  const fileToSend = _attachedFile;
  clearFile();

  pywebview.api.send_message(text, fileToSend).then(result => {
    clearInterval(_timerId);
    document.getElementById('chat-typing').style.display = 'none';
    _sending = false;
    document.getElementById('chat-send').disabled = false;

    if (result.error) {
      appendAssistantUI('⚠ Error: ' + result.error);
    } else {
      appendAssistantUI(result.content);
      if (result.degraded) {
         // Optionally append degraded UI
      }
    }
    loadSessions(); // refresh history list
    scrollBottom();
    ta.focus();
  });
}

function clearMessagesUI() {
  document.getElementById('chat-messages').innerHTML = '';
}

function appendUserUI(text) {
  const el = document.createElement('div');
  el.className = 'msg msg-user';
  const content = document.createElement('div');
  content.className = 'msg-content';
  content.innerHTML = `<div class="avatar avatar-user">U</div><div class="bubble"></div>`;
  const bubble = content.querySelector('.bubble');
  renderMarkdownLite(text, bubble);
  el.appendChild(content);
  document.getElementById('chat-messages').appendChild(el);
}

function appendAssistantUI(text) {
  const el = document.createElement('div');
  el.className = 'msg msg-assistant';
  const content = document.createElement('div');
  content.className = 'msg-content';
  content.innerHTML = `<div class="avatar avatar-ai">🐱</div><div class="bubble"></div>`;
  const bubble = content.querySelector('.bubble');
  renderMarkdownLite(text, bubble);
  
  const actions = document.createElement('div');
  actions.className = 'msg-actions';
  
  if (text.includes('# Slide')) {
    const pptBtn = document.createElement('button');
    pptBtn.innerHTML = '📽️ PPT';
    pptBtn.title = 'Export to PowerPoint';
    pptBtn.onclick = () => {
      pptBtn.innerHTML = '⌛';
      pywebview.api.export_ppt(text).then(r => {
        pptBtn.innerHTML = r.error ? '⚠' : '✓';
      });
    };
    actions.appendChild(pptBtn);
  }
  
  const copyBtn = document.createElement('button');
  copyBtn.innerHTML = '📋';
  copyBtn.title = 'Copy response';
  copyBtn.onclick = () => {
    navigator.clipboard.writeText(text).then(() => {
      copyBtn.innerHTML = '✓';
      setTimeout(() => copyBtn.innerHTML = '📋', 2000);
    });
  };
  actions.appendChild(copyBtn);
  
  bubble.appendChild(actions);
  el.appendChild(content);
  document.getElementById('chat-messages').appendChild(el);
}

function scrollBottom() {
  const c = document.getElementById('chat-messages');
  c.scrollTop = c.scrollHeight;
}

function renderMarkdownLite(text, container) {
  const parts = text.split(/```(.*?)[\r\n]+([\s\S]*?)```/g);
  for (let i = 0; i < parts.length; i++) {
    if (i % 3 === 0) {
      if (parts[i]) {
        const div = document.createElement('div');
        // Simple bold rendering
        let t = parts[i].replace(/\\*\\*(.*?)\\*\\*/g, '<strong>$1</strong>');
        div.innerHTML = t.replace(/\\n/g, '<br>');
        div.style.marginBottom = '8px';
        container.appendChild(div);
      }
    } else if (i % 3 === 1) {
      const lang = parts[i].trim();
      const code = parts[i+1];
      
      const preWrapper = document.createElement('div');
      
      const header = document.createElement('div');
      header.className = 'code-header';
      header.innerHTML = `<span>${lang}</span>`;
      
      const copyCodeBtn = document.createElement('button');
      copyCodeBtn.innerHTML = '📋 Copy Code';
      copyCodeBtn.onclick = () => {
        navigator.clipboard.writeText(code).then(() => {
          copyCodeBtn.innerHTML = '✓ Copied!';
          setTimeout(() => copyCodeBtn.innerHTML = '📋 Copy Code', 2000);
        });
      };
      header.appendChild(copyCodeBtn);
      
      const pre = document.createElement('pre');
      const codeEl = document.createElement('code');
      if (lang) codeEl.className = 'language-' + lang;
      codeEl.textContent = code;
      pre.appendChild(codeEl);
      
      preWrapper.appendChild(header);
      preWrapper.appendChild(pre);
      container.appendChild(preWrapper);
      
      // Apply syntax highlighting
      try { hljs.highlightElement(codeEl); } catch (e) {}
      
      i++; // skip the code part
    }
  }
}

function exportChat() {
  pywebview.api.export_chat().then(r => {
    alert(r.error ? 'Export failed: ' + r.error : 'Exported to: ' + r.path);
  });
}

// Schedule logic bindings...
function syncFields() {
  const t = document.getElementById('f-type').value;
  document.getElementById('f-day-wrap').style.display = t === 'weekly' ? '' : 'none';
  document.getElementById('f-time-wrap').style.display = t === 'hourly' ? 'none' : '';
  document.getElementById('f-minute-wrap').style.display = t === 'hourly' ? '' : 'none';
}
function submitForm() {
  const t = document.getElementById('f-type').value;
  const item = {
    id: document.getElementById('f-id').value || undefined,
    title: document.getElementById('f-title').value.trim(),
    type: t,
    lead_min: parseInt(document.getElementById('f-lead').value || '0', 10),
    enabled: true,
  };
  if (t === 'weekly') item.day = document.getElementById('f-day').value;
  if (t !== 'hourly') item.time = document.getElementById('f-time').value;
  if (t === 'hourly') item.minute = parseInt(document.getElementById('f-minute').value, 10);
  pywebview.api.upsert_schedule(item).then(r => {
    document.getElementById('f-msg').innerText = r.error ? ('⚠ ' + r.error) : 'Saved!';
    if (!r.error) { renderSchedule({items: r.items, errors: []}); resetForm(); }
  });
}
function renderSchedule(data) {
  const tb = document.getElementById('list');
  tb.innerHTML = '';
  for (const it of data.items) {
    const tr = document.createElement('tr');
    tr.className = 'rowline';
    tr.innerHTML = `<td><input type="checkbox" ${it.enabled ? 'checked' : ''}></td>
      <td>${it.title}</td><td>${it.type} ${it.time || ''}</td>
      <td><button class="del">Delete</button></td>`;
    tr.querySelector('input').onclick = (e) => {
      e.stopPropagation();
      it.enabled = e.target.checked;
      pywebview.api.upsert_schedule(it).then(r => renderSchedule({items: r.items, errors: []}));
    };
    tr.querySelector('.del').onclick = (e) => {
      e.stopPropagation();
      pywebview.api.delete_schedule(it.id).then(r => renderSchedule({items: r.items, errors: []}));
    };
    tr.onclick = () => {
      document.getElementById('f-id').value = it.id;
      document.getElementById('f-title').value = it.title;
      document.getElementById('f-type').value = it.type;
      syncFields();
    };
    tb.appendChild(tr);
  }
}
function resetForm() {
  document.getElementById('f-id').value = '';
  document.getElementById('f-title').value = '';
  document.getElementById('f-msg').innerText = '';
}

window.addEventListener('pywebviewready', () => {
  syncFields();
  pywebview.api.get_tab().then(t => showTab(t));
  pywebview.api.list_schedules().then(renderSchedule);
});
</script>
</body>
</html>
"""

with open('chat/chat.html', 'w', encoding='utf-8') as f:
    f.write(new_html)
print("chat.html fully updated!")
